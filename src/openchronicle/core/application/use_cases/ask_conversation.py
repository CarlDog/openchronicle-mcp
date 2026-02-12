from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from openchronicle.core.application.routing.router_policy import RouteDecision, RouterPolicy
from openchronicle.core.application.services.llm_execution import execute_with_route
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases import run_task
from openchronicle.core.domain.errors.error_codes import (
    CONNECTION_ERROR,
    NSFW_POOL_NOT_CONFIGURED,
    OUTBOUND_PII_BLOCKED,
    SELF_REPORT_INVALID,
    TIMEOUT,
)
from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.project import Event, Task
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.interaction_router_port import InteractionRouterPort
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.privacy_gate_port import PrivacyGatePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.infrastructure.config.settings import PrivacyOutboundSettings
from openchronicle.core.infrastructure.privacy.rule_privacy import is_external_provider
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


class TelemetryRecorder(Protocol):
    def telemetry_enabled(self) -> bool: ...

    def usage_enabled(self) -> bool: ...

    def perf_enabled(self) -> bool: ...

    def context_enabled(self) -> bool: ...

    def memory_enabled(self) -> bool: ...

    def memory_self_report_enabled(self) -> bool: ...

    def memory_self_report_max_ids(self) -> int: ...

    def memory_self_report_strict(self) -> bool: ...

    def record_llm_usage(self, *, provider: str, model: str, usage: LLMUsage | None) -> None: ...

    def record_llm_error(self, *, error_code: str | None) -> None: ...

    def record_perf(
        self,
        *,
        ask_total_ms: float | None = None,
        provider_call_ms: float | None = None,
        context_assemble_ms: float | None = None,
    ) -> None: ...

    def record_context(self, *, prompt_tokens: int | None, max_context_tokens: int | None) -> None: ...

    def record_memory_retrieval(
        self,
        *,
        retrieved_ids: Iterable[str],
        pinned_ids: Iterable[str],
        retrieved_chars_total: int,
    ) -> None: ...

    def record_memory_self_report(self, *, used_ids: Iterable[str], valid: bool) -> None: ...


def is_enqueueable_provider_failure(error_code: str | None) -> bool:
    """Return True when a provider failure should enqueue instead of erroring.

    Allowlisted codes:
    - CONNECTION_ERROR: provider unreachable
    - TIMEOUT: provider did not respond in time
    """
    if not error_code:
        return False
    return error_code in {CONNECTION_ERROR, TIMEOUT}


def _read_int_env(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _resolve_max_context_tokens() -> int | None:
    return _read_int_env(os.getenv("OC_LLM_CONTEXT_MAX_TOKENS"))


def _extract_meta_block(text: str) -> tuple[str, str | None]:
    start = text.rfind("<OC_META>")
    if start == -1:
        return text, None
    end = text.find("</OC_META>", start)
    if end == -1:
        return text, None
    meta_raw = text[start + len("<OC_META>") : end]
    cleaned = (text[:start] + text[end + len("</OC_META>") :]).strip()
    return cleaned, meta_raw.strip()


def _parse_used_memory_ids(
    meta_raw: str,
    *,
    retrieved_ids: set[str],
    max_ids: int,
) -> list[str] | None:
    try:
        payload = json.loads(meta_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    used_ids_value = payload.get("used_memory_ids")
    if not isinstance(used_ids_value, list):
        return None
    used_ids: list[str] = []
    for value in used_ids_value:
        if not isinstance(value, str):
            return None
        if value not in retrieved_ids:
            return None
        if value and value not in used_ids:
            used_ids.append(value)
        if len(used_ids) >= max_ids:
            break
    return used_ids


@dataclass
class PreparedContext:
    """Pre-computed context for a conversation turn.

    Produced by prepare_ask(), consumed by execute() and finalize_turn().
    The streaming path in chat.py uses this to get memory, privacy, routing,
    and telemetry without duplicating the pipeline.
    """

    conversation: Conversation
    prior_turns: list[Turn]
    messages: list[dict[str, str]]
    route_decision: RouteDecision
    effective_prompt: str
    retrieved_ids: list[str]
    self_report_enabled: bool
    prompt_text: str
    conversation_id: str
    max_output_tokens: int
    temperature: float
    started_at: float


async def prepare_ask(
    convo_store: ConversationStorePort,
    memory_store: MemoryStorePort,
    emit_event: Callable[[Event], None],
    conversation_id: str,
    prompt_text: str,
    *,
    interaction_router: InteractionRouterPort | None = None,
    last_n: int = 10,
    top_k_memory: int = 8,
    include_pinned_memory: bool = True,
    max_output_tokens: int = 512,
    temperature: float = 0.2,
    allow_pii: bool = False,
    privacy_gate: PrivacyGatePort | None = None,
    privacy_settings: PrivacyOutboundSettings | None = None,
    telemetry: TelemetryRecorder | None = None,
) -> PreparedContext:
    """Prepare context for a conversation turn (phases 1-5).

    Performs validation, memory retrieval, routing, privacy gating, and
    self-report injection. Returns a PreparedContext that can be used with
    either execute_with_route() or stream_with_route().
    """
    perf_enabled = telemetry is not None and telemetry.perf_enabled()
    started_at = time.perf_counter() if perf_enabled else 0.0
    context_started_at = started_at if perf_enabled else 0.0

    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    effective_mode = (conversation.mode or "general").strip().lower()
    if effective_mode not in {"general", "persona", "story"}:
        effective_mode = "general"

    prior_turns = convo_store.list_turns(conversation_id, limit=last_n)

    messages: list[dict[str, str]] = [{"role": "system", "content": "You are a helpful assistant."}]

    pinned_memory = memory_store.list_memory(limit=top_k_memory, pinned_only=True) if include_pinned_memory else []
    relevant_memory = memory_store.search_memory(
        prompt_text,
        top_k=top_k_memory,
        conversation_id=conversation_id,
        include_pinned=False,
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="memory.retrieved",
            payload={
                "pinned_count": len(pinned_memory),
                "relevant_count": len(relevant_memory),
                "pinned_ids": [item.id for item in pinned_memory],
                "relevant_ids": [item.id for item in relevant_memory],
                "query_len": len(prompt_text),
                "top_k": top_k_memory,
                "include_pinned_memory": include_pinned_memory,
            },
        )
    )

    if pinned_memory or relevant_memory:
        memory_lines: list[str] = []
        if include_pinned_memory:
            memory_lines.append("Pinned memory:")
            for item in pinned_memory:
                content_snippet = item.content if len(item.content) <= 300 else item.content[:300] + "..."
                tags_str = ",".join(item.tags)
                memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")
            memory_lines.append("")

        memory_lines.append("Relevant memory:")
        for item in relevant_memory:
            content_snippet = item.content if len(item.content) <= 300 else item.content[:300] + "..."
            tags_str = ",".join(item.tags)
            memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")

        messages.append({"role": "system", "content": "\n".join(memory_lines)})
    for turn in prior_turns:
        messages.append({"role": "user", "content": turn.user_text})
        messages.append({"role": "assistant", "content": turn.assistant_text})
    messages.append({"role": "user", "content": prompt_text})

    retrieved_ids = [item.id for item in pinned_memory] + [item.id for item in relevant_memory]
    pinned_ids = [item.id for item in pinned_memory]
    retrieved_chars_total = sum(len(item.content) for item in pinned_memory + relevant_memory)

    if telemetry is not None and telemetry.memory_enabled():
        telemetry.record_memory_retrieval(
            retrieved_ids=retrieved_ids,
            pinned_ids=pinned_ids,
            retrieved_chars_total=retrieved_chars_total,
        )

    if perf_enabled and telemetry is not None:
        context_assemble_ms = (time.perf_counter() - context_started_at) * 1000
        telemetry.record_perf(context_assemble_ms=context_assemble_ms)

    interaction_router = interaction_router or RuleInteractionRouter()
    router_hint = interaction_router.analyze(user_text=prompt_text, recent_turns=prior_turns)
    thresholds = _router_thresholds(interaction_router)

    reason_codes = router_hint.reason_codes if thresholds["router_log_reasons"] else []

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="router.invoked",
            payload={
                "effective_mode": effective_mode,
                "mode_hint": router_hint.mode_hint,
                "nsfw_score": router_hint.nsfw_score,
                "requires_nsfw_capable_model": router_hint.requires_nsfw_capable_model,
                "reason_codes": reason_codes,
                "nsfw_route_if_score_gte": thresholds["nsfw_route_if_score_gte"],
                "nsfw_uncertain_if_score_gte": thresholds["nsfw_uncertain_if_score_gte"],
                "persona_uncertain_routes_to_nsfw": thresholds["persona_uncertain_routes_to_nsfw"],
                "router_log_reasons": thresholds["router_log_reasons"],
            },
        )
    )

    router = RouterPolicy()
    if router_hint.requires_nsfw_capable_model and effective_mode in {"persona", "story"}:
        nsfw_pool = router.pool_config.nsfw_pool
        if not nsfw_pool:
            config_dir = os.getenv("OC_CONFIG_DIR", "config")
            configured_providers = _configured_providers(router.pool_config)
            emit_event(
                Event(
                    project_id=conversation.project_id,
                    task_id=conversation.id,
                    type="router.applied",
                    payload={
                        "applied": False,
                        "reason": "nsfw_pool_missing",
                        "pool": "NSFW",
                        "effective_mode": effective_mode,
                    },
                )
            )
            providers_str = ", ".join(configured_providers) if configured_providers else "none"
            raise LLMProviderError(
                "NSFW pool not configured",
                error_code=NSFW_POOL_NOT_CONFIGURED,
                hint=(
                    "Set OC_LLM_POOL_NSFW in your environment or config under OC_CONFIG_DIR="
                    f"{config_dir} to a pool that supports NSFW-capable persona/story mode. "
                    f"Configured providers: {providers_str}."
                ),
                configured_providers=configured_providers,
                details={
                    "config_dir": config_dir,
                    "configured_providers": configured_providers,
                    "fast_pool": _pool_candidates(router.pool_config.fast_pool),
                    "quality_pool": _pool_candidates(router.pool_config.quality_pool),
                    "nsfw_pool": _pool_candidates(router.pool_config.nsfw_pool),
                },
            )

        route_decision = router.route_with_pool(
            nsfw_pool,
            mode="nsfw",
            reasons=["router_nsfw_pool"],
        )
        emit_event(
            Event(
                project_id=conversation.project_id,
                task_id=conversation.id,
                type="router.applied",
                payload={
                    "applied": True,
                    "reason": "requires_nsfw_capable_model",
                    "pool": "NSFW",
                    "effective_mode": effective_mode,
                },
            )
        )
    else:
        route_decision = router.route(
            task_type="convo.ask",
            agent_role="user",
            agent_tags=None,
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=None,
            max_tokens_per_task=None,
            rate_limit_triggered=False,
            rpm_limit=None,
        )
        emit_event(
            Event(
                project_id=conversation.project_id,
                task_id=conversation.id,
                type="router.applied",
                payload={
                    "applied": False,
                    "reason": "not_required",
                    "effective_mode": effective_mode,
                },
            )
        )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_started",
            payload={"prompt_chars": len(prompt_text)},
        )
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="llm.routed",
            payload={
                "provider": route_decision.provider,
                "model": route_decision.model,
                "reasons": route_decision.reasons,
            },
        )
    )

    effective_prompt = prompt_text
    if allow_pii:
        emit_event(
            Event(
                project_id=conversation.project_id,
                task_id=conversation.id,
                type="privacy.override_used",
                payload={
                    "allow_pii": True,
                    "scope": "single_request",
                    "provider": route_decision.provider,
                    "conversation_id": conversation.id,
                },
            )
        )
    elif privacy_gate is not None and privacy_settings is not None:
        mode = privacy_settings.mode
        if mode != "off":
            should_check = True
            if privacy_settings.external_only:
                should_check = is_external_provider(route_decision.provider)
            if should_check:
                redacted_prompt, report = privacy_gate.analyze_and_apply(
                    text=prompt_text,
                    mode=mode,
                    redact_style=privacy_settings.redact_style,
                    categories=privacy_settings.categories,
                )
                categories = sorted(report.categories)
                counts = {category: report.counts[category] for category in categories}
                applies = True

                if privacy_settings.log_events:
                    emit_event(
                        Event(
                            project_id=conversation.project_id,
                            task_id=conversation.id,
                            type="privacy.outbound_checked",
                            payload={
                                "mode": report.action,
                                "external_only": privacy_settings.external_only,
                                "applies": applies,
                                "categories": categories,
                                "counts": counts,
                                "redactions_applied": report.redactions_applied,
                            },
                        )
                    )

                if report.action == "block":
                    raise LLMProviderError(
                        "Outbound privacy gate blocked external provider request.",
                        error_code=OUTBOUND_PII_BLOCKED,
                        hint=("Remove or redact PII, or change privacy_outbound_mode to warn/redact/off."),
                        details={"categories": report.categories, "counts": report.counts},
                    )

                if report.action == "redact":
                    effective_prompt = redacted_prompt

    self_report_enabled = telemetry is not None and telemetry.memory_self_report_enabled() and bool(retrieved_ids)
    if self_report_enabled:
        retrieved_ids_str = ",".join(retrieved_ids)
        effective_prompt = (
            f"{effective_prompt}\n\n"
            "Return your normal answer. Additionally append a final line containing: "
            '<OC_META>{"used_memory_ids":[...]}</OC_META> where used_memory_ids includes only IDs from: '
            f"[{retrieved_ids_str}]."
        )

    return PreparedContext(
        conversation=conversation,
        prior_turns=prior_turns,
        messages=messages,
        route_decision=route_decision,
        effective_prompt=effective_prompt,
        retrieved_ids=retrieved_ids,
        self_report_enabled=self_report_enabled,
        prompt_text=prompt_text,
        conversation_id=conversation_id,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        started_at=started_at,
    )


def _record_error_telemetry(
    ctx: PreparedContext,
    exc: LLMProviderError,
    provider_started_at: float,
    telemetry: TelemetryRecorder | None,
    emit_event: Callable[[Event], None],
) -> None:
    """Record telemetry and emit event for a failed LLM call."""
    perf_enabled = ctx.started_at > 0.0
    if perf_enabled and telemetry is not None:
        provider_call_ms = (time.perf_counter() - provider_started_at) * 1000
        telemetry.record_perf(provider_call_ms=provider_call_ms)
        ask_total_ms = (time.perf_counter() - ctx.started_at) * 1000
        telemetry.record_perf(ask_total_ms=ask_total_ms)
    if telemetry is not None and telemetry.usage_enabled():
        telemetry.record_llm_usage(
            provider=ctx.route_decision.provider,
            model=ctx.route_decision.model,
            usage=None,
        )
        telemetry.record_llm_error(error_code=exc.error_code)
    emit_event(
        Event(
            project_id=ctx.conversation.project_id,
            task_id=ctx.conversation.id,
            type="convo.turn_failed",
            payload={"error_code": exc.error_code, "hint": exc.hint},
        )
    )


async def finalize_turn(
    ctx: PreparedContext,
    assistant_text: str,
    response: LLMResponse | None,
    convo_store: ConversationStorePort,
    storage: StoragePort,
    emit_event: Callable[[Event], None],
    telemetry: TelemetryRecorder | None = None,
) -> Turn:
    """Finalize a conversation turn (phases 7-9).

    Performs self-report extraction, turn persistence, event emission, and
    telemetry recording. When response is None (streaming path), skips
    llm.completed event, record_llm_usage, and record_context.
    """
    used_memory_ids: list[str] | None = None
    if ctx.self_report_enabled:
        cleaned_text, meta_raw = _extract_meta_block(assistant_text)
        assistant_text = cleaned_text if meta_raw is not None else assistant_text
        retrieved_id_set = {value for value in ctx.retrieved_ids if value}
        if meta_raw is None:
            if telemetry is not None:
                telemetry.record_memory_self_report(used_ids=[], valid=False)
            if telemetry is not None and telemetry.memory_self_report_strict():
                raise LLMProviderError(
                    "Self-report metadata missing",
                    error_code=SELF_REPORT_INVALID,
                    hint="LLM did not provide <OC_META> self-report block.",
                )
        else:
            max_ids = telemetry.memory_self_report_max_ids() if telemetry is not None else 20
            parsed = _parse_used_memory_ids(meta_raw, retrieved_ids=retrieved_id_set, max_ids=max_ids)
            if parsed is None:
                if telemetry is not None:
                    telemetry.record_memory_self_report(used_ids=[], valid=False)
                if telemetry is not None and telemetry.memory_self_report_strict():
                    raise LLMProviderError(
                        "Self-report metadata invalid",
                        error_code=SELF_REPORT_INVALID,
                        hint="Self-report must include valid used_memory_ids from retrieved set.",
                    )
            else:
                used_memory_ids = parsed
                if telemetry is not None:
                    telemetry.record_memory_self_report(used_ids=used_memory_ids, valid=True)
                emit_event(
                    Event(
                        project_id=ctx.conversation.project_id,
                        task_id=ctx.conversation.id,
                        type="memory.used_reported",
                        payload={
                            "retrieved_ids_count": len(ctx.retrieved_ids),
                            "used_ids_count": len(used_memory_ids),
                            "used_memory_ids": used_memory_ids,
                            "strict_enabled": bool(telemetry is not None and telemetry.memory_self_report_strict()),
                        },
                    )
                )

    if response is not None:
        if telemetry is not None and telemetry.usage_enabled():
            telemetry.record_llm_usage(provider=response.provider, model=response.model, usage=response.usage)

        if telemetry is not None and telemetry.context_enabled():
            prompt_tokens = response.usage.input_tokens if response.usage else None
            max_context_tokens = _resolve_max_context_tokens()
            telemetry.record_context(prompt_tokens=prompt_tokens, max_context_tokens=max_context_tokens)

        emit_event(
            Event(
                project_id=ctx.conversation.project_id,
                task_id=ctx.conversation.id,
                type="llm.completed",
                payload={
                    "provider": response.provider,
                    "model": response.model,
                    "request_id": response.request_id,
                    "finish_reason": response.finish_reason,
                    "latency_ms": response.latency_ms,
                    "usage": {
                        "input_tokens": response.usage.input_tokens if response.usage else None,
                        "output_tokens": response.usage.output_tokens if response.usage else None,
                        "total_tokens": response.usage.total_tokens if response.usage else None,
                    },
                },
            )
        )

    with storage.transaction():
        turn_index = convo_store.next_turn_index(ctx.conversation_id)
        turn = Turn(
            conversation_id=ctx.conversation_id,
            turn_index=turn_index,
            user_text=ctx.prompt_text,
            assistant_text=assistant_text,
            provider=ctx.route_decision.provider,
            model=ctx.route_decision.model,
            routing_reasons=ctx.route_decision.reasons,
        )
        convo_store.add_turn(turn)

    emit_event(
        Event(
            project_id=ctx.conversation.project_id,
            task_id=ctx.conversation.id,
            type="convo.turn_completed",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "provider": turn.provider,
                "model": turn.model,
            },
        )
    )

    if ctx.started_at > 0.0 and telemetry is not None:
        ask_total_ms = (time.perf_counter() - ctx.started_at) * 1000
        telemetry.record_perf(ask_total_ms=ask_total_ms)

    return turn


async def execute(
    convo_store: ConversationStorePort,
    storage: StoragePort,
    memory_store: MemoryStorePort,
    llm: LLMPort,
    emit_event: Callable[[Event], None],
    conversation_id: str,
    prompt_text: str,
    *,
    interaction_router: InteractionRouterPort | None = None,
    last_n: int = 10,
    top_k_memory: int = 8,
    include_pinned_memory: bool = True,
    max_output_tokens: int = 512,
    temperature: float = 0.2,
    allow_pii: bool = False,
    privacy_gate: PrivacyGatePort | None = None,
    privacy_settings: PrivacyOutboundSettings | None = None,
    telemetry: TelemetryRecorder | None = None,
) -> Turn:
    ctx = await prepare_ask(
        convo_store=convo_store,
        memory_store=memory_store,
        emit_event=emit_event,
        conversation_id=conversation_id,
        prompt_text=prompt_text,
        interaction_router=interaction_router,
        last_n=last_n,
        top_k_memory=top_k_memory,
        include_pinned_memory=include_pinned_memory,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        allow_pii=allow_pii,
        privacy_gate=privacy_gate,
        privacy_settings=privacy_settings,
        telemetry=telemetry,
    )

    perf_enabled = ctx.started_at > 0.0
    provider_started_at = time.perf_counter() if perf_enabled else 0.0
    try:
        response = await execute_with_route(
            llm,
            ctx.route_decision,
            ctx.messages[:-1] + [{"role": "user", "content": ctx.effective_prompt}],
            max_output_tokens=ctx.max_output_tokens,
            temperature=ctx.temperature,
        )
    except LLMProviderError as exc:
        _record_error_telemetry(ctx, exc, provider_started_at, telemetry, emit_event)
        raise

    if perf_enabled and telemetry is not None:
        provider_call_ms = (time.perf_counter() - provider_started_at) * 1000
        telemetry.record_perf(provider_call_ms=provider_call_ms)

    return await finalize_turn(
        ctx=ctx,
        assistant_text=response.content,
        response=response,
        convo_store=convo_store,
        storage=storage,
        emit_event=emit_event,
        telemetry=telemetry,
    )


def enqueue(
    orchestrator: OrchestratorService,
    *,
    convo_store: ConversationStorePort,
    conversation_id: str,
    prompt_text: str,
    include_explain: bool,
    allow_pii: bool,
    metadata: dict[str, object] | None,
    interaction_router: InteractionRouterPort | None,
    emit_event: Callable[[Event], None],
) -> Task:
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    recent_turns = convo_store.list_turns(conversation_id, limit=10)
    effective_mode = (conversation.mode or "general").strip().lower()
    if effective_mode not in {"general", "persona", "story"}:
        effective_mode = "general"

    router = RouterPolicy()
    router_hint = (interaction_router or RuleInteractionRouter()).analyze(
        user_text=prompt_text,
        recent_turns=recent_turns,
    )
    if router_hint.requires_nsfw_capable_model and effective_mode in {"persona", "story"}:
        nsfw_pool = router.pool_config.nsfw_pool
        if not nsfw_pool:
            config_dir = os.getenv("OC_CONFIG_DIR", "config")
            configured_providers = _configured_providers(router.pool_config)
            providers_str = ", ".join(configured_providers) if configured_providers else "none"
            raise LLMProviderError(
                "NSFW pool not configured",
                error_code=NSFW_POOL_NOT_CONFIGURED,
                hint=(
                    "Set OC_LLM_POOL_NSFW in your environment or config under OC_CONFIG_DIR="
                    f"{config_dir} to a pool that supports NSFW-capable persona/story mode. "
                    f"Configured providers: {providers_str}."
                ),
                configured_providers=configured_providers,
                details={
                    "config_dir": config_dir,
                    "configured_providers": configured_providers,
                    "fast_pool": _pool_candidates(router.pool_config.fast_pool),
                    "quality_pool": _pool_candidates(router.pool_config.quality_pool),
                    "nsfw_pool": _pool_candidates(router.pool_config.nsfw_pool),
                },
            )

    task_payload: dict[str, object] = {
        "conversation_id": conversation_id,
        "prompt": prompt_text,
        "explain": include_explain,
        "allow_pii": allow_pii,
    }
    if metadata is not None:
        task_payload["metadata"] = metadata

    task = run_task.submit(
        orchestrator,
        project_id=conversation.project_id,
        task_type="convo.ask",
        payload=task_payload,
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=task.id,
            type="convo.ask_queued",
            payload={
                "conversation_id": conversation_id,
                "explain": include_explain,
                "allow_pii": allow_pii,
            },
        )
    )

    return task


def _router_thresholds(router: InteractionRouterPort) -> dict[str, object]:
    return {
        "nsfw_route_if_score_gte": getattr(
            router, "nsfw_route_if_score_gte", _read_float("OC_ROUTER_NSFW_ROUTE_GTE", 0.70)
        ),
        "nsfw_uncertain_if_score_gte": getattr(
            router, "nsfw_uncertain_if_score_gte", _read_float("OC_ROUTER_NSFW_UNCERTAIN_GTE", 0.45)
        ),
        "persona_uncertain_routes_to_nsfw": getattr(
            router, "persona_uncertain_routes_to_nsfw", _read_bool("OC_ROUTER_PERSONA_UNCERTAIN_TO_NSFW", True)
        ),
        "router_log_reasons": getattr(router, "router_log_reasons", _read_bool("OC_ROUTER_LOG_REASONS", False)),
    }


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip() not in {"0", "false", "False", "no"}


def _pool_candidates(pool: Iterable[object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for candidate in pool:
        provider = getattr(candidate, "provider", None)
        model = getattr(candidate, "model", None)
        weight = getattr(candidate, "weight", None)
        results.append({"provider": provider, "model": model, "weight": weight})
    return results


def _configured_providers(pool_config: object) -> list[str]:
    providers: set[str] = set()
    for pool_name in ("fast_pool", "quality_pool", "nsfw_pool"):
        pool = getattr(pool_config, pool_name, [])
        for candidate in pool:
            provider = getattr(candidate, "provider", None)
            if isinstance(provider, str) and provider:
                providers.add(provider)
    return sorted(providers)
