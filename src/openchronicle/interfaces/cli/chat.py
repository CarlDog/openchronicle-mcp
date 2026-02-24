"""Interactive chat REPL for OpenChronicle conversations."""

from __future__ import annotations

import argparse
import asyncio

from openchronicle.core.application.use_cases import ask_conversation, create_conversation
from openchronicle.core.application.use_cases.ask_conversation import TelemetryRecorder
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.wiring.container import CoreContainer


async def _stream_turn(
    container: CoreContainer,
    conversation_id: str,
    prompt: str,
    telemetry: TelemetryRecorder | None = None,
) -> str:
    """Stream a single turn, printing tokens as they arrive. Returns full text.

    Uses the full prepare/finalize pipeline so streaming gets memory retrieval,
    privacy gating, router analysis, self-report extraction, and telemetry.
    """
    from openchronicle.core.application.services.llm_execution import stream_with_route

    cs = container.conversation_settings
    ctx = await ask_conversation.prepare_ask(
        convo_store=container.storage,
        memory_store=container.storage,
        emit_event=container.event_logger.append,
        conversation_id=conversation_id,
        prompt_text=prompt,
        interaction_router=container.interaction_router,
        router_policy=container.router_policy,
        last_n=cs.last_n,
        top_k_memory=cs.top_k_memory,
        include_pinned_memory=cs.include_pinned_memory,
        max_output_tokens=cs.max_output_tokens,
        temperature=cs.temperature,
        privacy_gate=getattr(container, "privacy_gate", None),
        privacy_settings=getattr(container, "privacy_settings", None),
        telemetry=telemetry,
    )

    collected: list[str] = []
    async for chunk in stream_with_route(
        container.llm,
        ctx.route_decision,
        ctx.messages[:-1] + [{"role": "user", "content": ctx.effective_prompt}],
        max_output_tokens=ctx.max_output_tokens,
        temperature=ctx.temperature,
    ):
        if chunk.text:
            print(chunk.text, end="", flush=True)
            collected.append(chunk.text)
    print()  # newline after streaming

    turn = await ask_conversation.finalize_turn(
        ctx=ctx,
        assistant_text="".join(collected),
        response=None,
        convo_store=container.storage,
        storage=container.storage,
        emit_event=container.event_logger.append,
        telemetry=telemetry,
    )

    return turn.assistant_text


async def chat_loop(container: CoreContainer, conversation_id: str, *, stream: bool = True, moe: bool = False) -> int:
    """Interactive chat REPL."""
    from openchronicle.interfaces.cli.stdio import MetricsTracker

    telemetry: TelemetryRecorder = MetricsTracker(telemetry=container.telemetry_settings)

    label = f"Chat ({conversation_id[:8]}...)"
    if moe:
        label += " [MoE]"
    print(f"{label} — type /quit to exit")
    while True:
        try:
            user_input = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped in ("/quit", "/exit", "/q"):
            break

        try:
            if stream:
                print()
                await _stream_turn(container, conversation_id, stripped, telemetry=telemetry)
            else:
                cs = container.conversation_settings
                turn = await ask_conversation.execute(
                    convo_store=container.storage,
                    storage=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.event_logger.append,
                    conversation_id=conversation_id,
                    prompt_text=stripped,
                    router_policy=container.router_policy,
                    last_n=cs.last_n,
                    top_k_memory=cs.top_k_memory,
                    include_pinned_memory=cs.include_pinned_memory,
                    max_output_tokens=cs.max_output_tokens,
                    temperature=cs.temperature,
                    allow_pii=False,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                    telemetry=telemetry,
                    moe=moe,
                )
                print(f"\n{turn.assistant_text}")
        except (ValueError, LLMProviderError) as exc:
            print(f"\nError: {exc}")
            continue

    return 0


def _resolve_conversation(args: argparse.Namespace, container: CoreContainer) -> str | None:
    """Resolve conversation ID from args, returning None on error."""
    if args.conversation_id:
        return str(args.conversation_id)

    if args.resume:
        convos = container.storage.list_conversations(limit=1)
        if not convos:
            print("No conversations to resume. Start a new one with: oc chat")
            return None
        print(f"Resuming: {convos[0].title or '(untitled)'} ({convos[0].id[:8]}...)")
        return convos[0].id

    conversation = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title=args.title or "Chat session",
    )
    return conversation.id


def cmd_chat(args: argparse.Namespace, container: CoreContainer) -> int:
    """oc chat [--conversation-id ID] [--resume] [--title TITLE] [--no-stream] [--moe]"""
    convo_id = _resolve_conversation(args, container)
    if convo_id is None:
        return 1
    moe = getattr(args, "moe", False)
    stream = not getattr(args, "no_stream", False)
    if moe:
        stream = False  # MoE V0 is non-streaming
    return asyncio.run(chat_loop(container, convo_id, stream=stream, moe=moe))
