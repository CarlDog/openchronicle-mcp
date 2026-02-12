"""Interactive chat REPL for OpenChronicle conversations."""

from __future__ import annotations

import argparse
import asyncio

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import ask_conversation, create_conversation
from openchronicle.core.domain.ports.llm_port import LLMProviderError


async def chat_loop(container: CoreContainer, conversation_id: str) -> int:
    """Interactive chat REPL."""
    print(f"Chat ({conversation_id[:8]}...) — type /quit to exit")
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
            turn = await ask_conversation.execute(
                convo_store=container.storage,
                storage=container.storage,
                memory_store=container.storage,
                llm=container.llm,
                interaction_router=container.interaction_router,
                emit_event=container.event_logger.append,
                conversation_id=conversation_id,
                prompt_text=stripped,
                last_n=10,
                top_k_memory=8,
                include_pinned_memory=True,
                allow_pii=False,
                privacy_gate=getattr(container, "privacy_gate", None),
                privacy_settings=getattr(container, "privacy_settings", None),
            )
        except (ValueError, LLMProviderError) as exc:
            print(f"\nError: {exc}")
            continue

        print(f"\n{turn.assistant_text}")

    return 0


def cmd_chat(args: argparse.Namespace, container: CoreContainer) -> int:
    """oc chat [--conversation-id ID] [--title TITLE]"""
    convo_id = args.conversation_id
    if convo_id is None:
        conversation = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
            title=args.title or "Chat session",
        )
        convo_id = conversation.id
    return asyncio.run(chat_loop(container, convo_id))
