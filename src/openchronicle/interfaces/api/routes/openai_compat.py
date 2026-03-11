"""OpenAI-compatible API — /v1/models and /v1/chat/completions.

V1 (passthrough): ``/v1/models``, ``/v1/chat/completions`` — no memory,
no conversations, no persistence.

V2 (persistent): ``/v1/p/{project_id}/...`` — memory injection via
``assemble_context``, turn recording via ``external_turn``, rolling
webui session per project or explicit conversation scoping.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from openchronicle.core.application.routing.router_policy import RouteDecision
from openchronicle.core.application.services.llm_execution import (
    execute_with_route,
    stream_with_route,
)
from openchronicle.core.application.use_cases import assemble_context, external_turn
from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container

logger = logging.getLogger(__name__)

router = APIRouter()

ContainerDep = Annotated[CoreContainer, Depends(get_container)]

# Fixed epoch for model "created" timestamps (models don't have creation dates).
_MODEL_EPOCH = 1_700_000_000

# System prompt for webui-mode conversations (replaces generic "You are a helpful assistant").
_OC_WEBUI_SYSTEM_PROMPT = (
    "You are an OpenChronicle assistant. You have access to the user's "
    "collected data, conversation history, and memory items through the "
    "context provided. Answer questions about this data accurately and "
    "helpfully."
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str = Field(min_length=1, max_length=50)
    content: str = Field(max_length=200_000)


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="auto", max_length=200)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_route(container: CoreContainer, model_id: str) -> RouteDecision:
    """Turn an OpenAI-style model string into an OC RouteDecision.

    ``"auto"`` delegates to the default pool router.
    ``"provider/model"`` targets a specific provider and model.
    """
    if model_id in ("auto", "openchronicle"):
        return container.router_policy.route(
            task_type="openai_compat",
            agent_role="worker",
        )

    if "/" not in model_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown model '{model_id}'. Use 'auto' for default routing "
                "or 'provider/model' format (e.g. 'openai/gpt-4o')."
            ),
        )

    provider, model = model_id.split("/", 1)

    # Validate the model exists in config
    entries = container.model_config_loader.list_enabled()
    match = any(e.provider == provider and e.model == model for e in entries)
    if not match:
        available = [f"{e.provider}/{e.model}" for e in entries]
        raise HTTPException(
            status_code=404,
            detail=(f"Model '{model_id}' not found. Available models: {available}"),
        )

    return RouteDecision(
        provider=provider,
        model=model,
        mode="explicit",
        reasons=[f"openai_compat:explicit:{model_id}"],
    )


def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Convert Pydantic ChatMessage list to plain dicts for the LLM port."""
    return [{"role": m.role, "content": m.content} for m in messages]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/models")
def list_models(container: ContainerDep) -> dict[str, Any]:
    """List available models in OpenAI format."""
    entries = container.model_config_loader.list_enabled()
    data = [
        {
            "id": f"{entry.provider}/{entry.model}",
            "object": "model",
            "created": _MODEL_EPOCH,
            "owned_by": entry.provider,
        }
        for entry in entries
    ]
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    container: ContainerDep,
) -> Any:
    """Create a chat completion (streaming or non-streaming)."""
    route = _resolve_route(container, body.model)
    messages = _messages_to_dicts(body.messages)
    model_label = f"{route.provider}/{route.model}"

    if body.stream:
        return _streaming_response(container, route, messages, model_label, body)

    return await _non_streaming_response(container, route, messages, model_label, body)


async def _non_streaming_response(
    container: CoreContainer,
    route: RouteDecision,
    messages: list[dict[str, str]],
    model_label: str,
    body: ChatCompletionRequest,
) -> dict[str, Any]:
    """Execute a non-streaming chat completion and return OpenAI format."""
    try:
        response = await execute_with_route(
            llm=container.llm,
            route_decision=route,
            messages=messages,
            max_output_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except LLMProviderError as exc:
        logger.warning("OpenAI compat LLM error: %s", exc)
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=str(exc),
        ) from exc

    usage = response.usage
    return {
        "id": f"chatcmpl-{uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_label,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": response.finish_reason or "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.input_tokens or 0 if usage else 0,
            "completion_tokens": usage.output_tokens or 0 if usage else 0,
            "total_tokens": usage.total_tokens or 0 if usage else 0,
        },
    }


def _streaming_response(
    container: CoreContainer,
    route: RouteDecision,
    messages: list[dict[str, str]],
    model_label: str,
    body: ChatCompletionRequest,
) -> StreamingResponse:
    """Return a StreamingResponse wrapping the SSE async generator."""
    completion_id = f"chatcmpl-{uuid4().hex[:12]}"

    async def event_generator() -> Any:
        created = int(time.time())
        first = True

        try:
            async for chunk in stream_with_route(
                llm=container.llm,
                route_decision=route,
                messages=messages,
                max_output_tokens=body.max_tokens,
                temperature=body.temperature,
            ):
                if first:
                    # First chunk includes role
                    delta: dict[str, str] = {"role": "assistant"}
                    if chunk.text:
                        delta["content"] = chunk.text
                    first = False
                elif chunk.finished:
                    delta = {}
                else:
                    delta = {"content": chunk.text} if chunk.text else {}

                finish_reason = chunk.finish_reason if chunk.finished else None
                if chunk.finished and not finish_reason:
                    finish_reason = "stop"

                sse_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_label,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "finish_reason": finish_reason,
                        }
                    ],
                }
                yield f"data: {json.dumps(sse_data)}\n\n"

            yield "data: [DONE]\n\n"
        except LLMProviderError as exc:
            logger.warning("OpenAI compat streaming error: %s", exc)
            error_data = {
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "code": exc.error_code or "PROVIDER_ERROR",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# V2 — Persistent endpoints (memory + turn recording)
# ---------------------------------------------------------------------------


def _get_or_create_webui_session(container: CoreContainer, project_id: str) -> Conversation:
    """Find the rolling webui conversation for a project, or create one."""
    project = container.storage.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    convos = container.storage.list_conversations(project_id=project_id)
    for c in convos:
        if c.mode == "webui":
            return c

    conversation = Conversation(
        project_id=project_id,
        title="Open WebUI Session",
        mode="webui",
    )
    container.storage.add_conversation(conversation)
    container.emit_event(
        Event(
            project_id=project_id,
            task_id=conversation.id,
            type="convo.created",
            payload={
                "conversation_id": conversation.id,
                "title": conversation.title,
                "source": "openai_compat",
            },
        )
    )
    return conversation


def _validate_project_conversation(
    container: CoreContainer,
    project_id: str,
    conversation_id: str,
) -> Conversation:
    """Validate project exists and conversation belongs to it."""
    project = container.storage.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    conversation = container.storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    if conversation.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{conversation_id}' not in project '{project_id}'",
        )

    return conversation


def _extract_last_user_message(messages: list[ChatMessage]) -> str:
    """Extract the last user message from OpenAI-format messages."""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return messages[-1].content  # Fallback: use last message regardless of role


def _build_oc_messages(
    container: CoreContainer,
    conversation_id: str,
    prompt_text: str,
) -> list[dict[str, str]]:
    """Assemble OC context (memory + turns + time) for the conversation."""
    ctx = assemble_context.execute(
        convo_store=container.storage,
        memory_store=container.storage,
        conversation_id=conversation_id,
        prompt_text=prompt_text,
        embedding_service=container.embedding_service,
    )
    # Replace generic system prompt with OC management prompt
    if ctx.messages and ctx.messages[0].get("role") == "system":
        ctx.messages[0] = {"role": "system", "content": _OC_WEBUI_SYSTEM_PROMPT}
    return ctx.messages


def _record_turn(
    container: CoreContainer,
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    provider: str,
    model: str,
) -> None:
    """Record the turn via external_turn use case. Best-effort — log errors, don't raise."""
    try:
        external_turn.execute(
            convo_store=container.storage,
            storage=container.storage,
            emit_event=container.emit_event,
            conversation_id=conversation_id,
            user_text=user_text,
            assistant_text=assistant_text,
            provider=provider,
            model=model,
        )
    except Exception:
        logger.exception("Failed to record turn for conversation %s", conversation_id)


# -- V2 models endpoints (Open WebUI base URL compat) --


def _list_models_with_oc(container: CoreContainer) -> dict[str, Any]:
    """List models with a synthetic ``openchronicle`` entry prepended.

    The ``openchronicle`` model routes through OC's default routing policy,
    giving Open WebUI a guaranteed model to select even when no provider
    configs are present.
    """
    result = list_models(container)
    oc_model = {
        "id": "openchronicle",
        "object": "model",
        "created": _MODEL_EPOCH,
        "owned_by": "openchronicle",
    }
    result["data"] = [oc_model, *result["data"]]
    return result


@router.get("/p/{project_id}/models")
def list_models_project(
    container: ContainerDep,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> dict[str, Any]:
    """List models at project scope with synthetic OC model prepended."""
    return _list_models_with_oc(container)


@router.get("/p/{project_id}/c/{conversation_id}/models")
def list_models_conversation(
    container: ContainerDep,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    conversation_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> dict[str, Any]:
    """List models at conversation scope with synthetic OC model prepended."""
    return _list_models_with_oc(container)


# -- V2 chat completions endpoints --


@router.post("/p/{project_id}/chat/completions")
async def chat_completions_project(
    body: ChatCompletionRequest,
    container: ContainerDep,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> Any:
    """Auto-session chat completion with memory injection and turn recording."""
    conversation = _get_or_create_webui_session(container, project_id)
    return await _persistent_chat(container, conversation, body)


@router.post("/p/{project_id}/c/{conversation_id}/chat/completions")
async def chat_completions_conversation(
    body: ChatCompletionRequest,
    container: ContainerDep,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    conversation_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> Any:
    """Explicit conversation chat completion with memory injection and turn recording."""
    conversation = _validate_project_conversation(container, project_id, conversation_id)
    return await _persistent_chat(container, conversation, body)


async def _passthrough_without_recording(
    container: CoreContainer,
    body: ChatCompletionRequest,
    prompt_text: str,
) -> Any:
    """Handle synthetic prompts (e.g., Open WebUI follow-up tasks) without memory or recording.

    Routes through the LLM but skips context assembly and turn persistence,
    preventing synthetic messages from polluting conversation history.
    """
    route = _resolve_route(container, body.model)
    openai_messages = [{"role": m.role, "content": m.content} for m in body.messages]
    model_label = f"{route.provider}/{route.model}"

    if body.stream:
        return _streaming_response(container, route, openai_messages, model_label, body)

    return await _non_streaming_response(container, route, openai_messages, model_label, body)


async def _persistent_chat(
    container: CoreContainer,
    conversation: Conversation,
    body: ChatCompletionRequest,
) -> Any:
    """Core handler for persistent (V2) chat completions.

    Filters out synthetic prompts injected by Open WebUI (e.g.,
    follow-up suggestion tasks) to prevent turn pollution.
    """
    prompt_text = _extract_last_user_message(body.messages)

    # Skip synthetic Open WebUI prompts — don't record or process
    if prompt_text.lstrip().startswith("### Task:"):
        return await _passthrough_without_recording(container, body, prompt_text)

    messages = _build_oc_messages(container, conversation.id, prompt_text)
    route = _resolve_route(container, body.model)
    model_label = f"{route.provider}/{route.model}"

    if body.stream:
        return _persistent_streaming_response(container, conversation, route, messages, model_label, body, prompt_text)

    return await _persistent_non_streaming_response(
        container, conversation, route, messages, model_label, body, prompt_text
    )


async def _persistent_non_streaming_response(
    container: CoreContainer,
    conversation: Conversation,
    route: RouteDecision,
    messages: list[dict[str, str]],
    model_label: str,
    body: ChatCompletionRequest,
    prompt_text: str,
) -> dict[str, Any]:
    """Non-streaming persistent chat: LLM call + turn recording."""
    try:
        response = await execute_with_route(
            llm=container.llm,
            route_decision=route,
            messages=messages,
            max_output_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except LLMProviderError as exc:
        logger.warning("OpenAI compat V2 LLM error: %s", exc)
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=str(exc),
        ) from exc

    _record_turn(
        container,
        conversation.id,
        prompt_text,
        response.content,
        route.provider,
        route.model,
    )

    usage = response.usage
    return {
        "id": f"chatcmpl-{uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_label,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": response.finish_reason or "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.input_tokens or 0 if usage else 0,
            "completion_tokens": usage.output_tokens or 0 if usage else 0,
            "total_tokens": usage.total_tokens or 0 if usage else 0,
        },
    }


def _persistent_streaming_response(
    container: CoreContainer,
    conversation: Conversation,
    route: RouteDecision,
    messages: list[dict[str, str]],
    model_label: str,
    body: ChatCompletionRequest,
    prompt_text: str,
) -> StreamingResponse:
    """Streaming persistent chat: SSE + buffered turn recording after [DONE]."""
    completion_id = f"chatcmpl-{uuid4().hex[:12]}"

    async def event_generator() -> Any:
        created = int(time.time())
        first = True
        buffer: list[str] = []

        try:
            async for chunk in stream_with_route(
                llm=container.llm,
                route_decision=route,
                messages=messages,
                max_output_tokens=body.max_tokens,
                temperature=body.temperature,
            ):
                if first:
                    delta: dict[str, str] = {"role": "assistant"}
                    if chunk.text:
                        delta["content"] = chunk.text
                        buffer.append(chunk.text)
                    first = False
                elif chunk.finished:
                    delta = {}
                else:
                    delta = {"content": chunk.text} if chunk.text else {}
                    if chunk.text:
                        buffer.append(chunk.text)

                finish_reason = chunk.finish_reason if chunk.finished else None
                if chunk.finished and not finish_reason:
                    finish_reason = "stop"

                sse_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_label,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "finish_reason": finish_reason,
                        }
                    ],
                }
                yield f"data: {json.dumps(sse_data)}\n\n"

            yield "data: [DONE]\n\n"

            # Record turn after streaming completes
            full_response = "".join(buffer)
            if full_response:
                _record_turn(
                    container,
                    conversation.id,
                    prompt_text,
                    full_response,
                    route.provider,
                    route.model,
                )

        except LLMProviderError as exc:
            logger.warning("OpenAI compat V2 streaming error: %s", exc)
            error_data = {
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "code": exc.error_code or "PROVIDER_ERROR",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
