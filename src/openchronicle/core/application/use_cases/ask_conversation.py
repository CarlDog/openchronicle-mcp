from __future__ import annotations

import os
from collections.abc import Callable, Iterable

from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.services.llm_execution import execute_with_route
from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.interaction_router_port import InteractionRouterPort
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.privacy_gate_port import PrivacyGatePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.infrastructure.config.settings import PrivacyOutboundSettings
from openchronicle.core.infrastructure.privacy.rule_privacy import is_external_provider
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


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
) -> Turn:
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
                error_code="NSFW_POOL_NOT_CONFIGURED",
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
                        error_code="OUTBOUND_PII_BLOCKED",
                        hint=("Remove or redact PII, or change privacy_outbound_mode to warn/redact/off."),
                        details={"categories": report.categories, "counts": report.counts},
                    )

                if report.action == "redact":
                    effective_prompt = redacted_prompt

    try:
        response = await execute_with_route(
            llm,
            route_decision,
            messages[:-1] + [{"role": "user", "content": effective_prompt}],
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    except LLMProviderError as exc:
        emit_event(
            Event(
                project_id=conversation.project_id,
                task_id=conversation.id,
                type="convo.turn_failed",
                payload={"error_code": exc.error_code, "hint": exc.hint},
            )
        )
        raise

    assistant_text = response.content

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
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
        turn_index = convo_store.next_turn_index(conversation_id)
        turn = Turn(
            conversation_id=conversation_id,
            turn_index=turn_index,
            user_text=prompt_text,
            assistant_text=assistant_text,
            provider=route_decision.provider,
            model=route_decision.model,
            routing_reasons=route_decision.reasons,
        )
        convo_store.add_turn(turn)

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_completed",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "provider": turn.provider,
                "model": turn.model,
            },
        )
    )

    return turn


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
