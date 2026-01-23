from __future__ import annotations

import os

from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.interaction_hint import InteractionHint
from openchronicle.core.domain.ports.interaction_router_port import InteractionRouterPort

_DEFAULT_ROUTER_ENABLED = True
_DEFAULT_ROUTER_LOG_REASONS = False
_DEFAULT_NSFW_ROUTE_GTE = 0.70
_DEFAULT_NSFW_UNCERTAIN_GTE = 0.45
_DEFAULT_PERSONA_UNCERTAIN_TO_NSFW = True

_PERSONA_MARKERS = [
    "roleplay",
    "in-character",
    "you are",
    "act as",
]

_STORY_MARKERS = [
    "scene:",
    "narration:",
    "chapter",
    "describe the scene",
]

_EXPLICIT_NSFW_TOKENS = [
    "sex",
    "explicit",
    "nude",
    "nudes",
    "porn",
    "oral",
    "penetration",
]

_AMBIGUOUS_NSFW_TOKENS = [
    "kiss",
    "kissing",
    "cuddle",
    "cuddling",
    "touch",
    "sensual",
    "intimate",
]


class RuleInteractionRouter(InteractionRouterPort):
    def __init__(
        self,
        *,
        router_enabled: bool | None = None,
        router_log_reasons: bool | None = None,
        nsfw_route_if_score_gte: float | None = None,
        nsfw_uncertain_if_score_gte: float | None = None,
        persona_uncertain_routes_to_nsfw: bool | None = None,
    ) -> None:
        self.router_enabled = _read_bool("OC_ROUTER_ENABLED", _DEFAULT_ROUTER_ENABLED)
        if router_enabled is not None:
            self.router_enabled = router_enabled

        self.router_log_reasons = _read_bool("OC_ROUTER_LOG_REASONS", _DEFAULT_ROUTER_LOG_REASONS)
        if router_log_reasons is not None:
            self.router_log_reasons = router_log_reasons

        self.nsfw_route_if_score_gte = _read_float("OC_ROUTER_NSFW_ROUTE_GTE", _DEFAULT_NSFW_ROUTE_GTE)
        if nsfw_route_if_score_gte is not None:
            self.nsfw_route_if_score_gte = nsfw_route_if_score_gte

        self.nsfw_uncertain_if_score_gte = _read_float("OC_ROUTER_NSFW_UNCERTAIN_GTE", _DEFAULT_NSFW_UNCERTAIN_GTE)
        if nsfw_uncertain_if_score_gte is not None:
            self.nsfw_uncertain_if_score_gte = nsfw_uncertain_if_score_gte

        self.persona_uncertain_routes_to_nsfw = _read_bool(
            "OC_ROUTER_PERSONA_UNCERTAIN_TO_NSFW", _DEFAULT_PERSONA_UNCERTAIN_TO_NSFW
        )
        if persona_uncertain_routes_to_nsfw is not None:
            self.persona_uncertain_routes_to_nsfw = persona_uncertain_routes_to_nsfw

    def analyze(self, *, user_text: str, recent_turns: list[Turn] | None = None) -> InteractionHint:
        _ = recent_turns
        if not self.router_enabled:
            return InteractionHint(
                mode_hint="general",
                nsfw_score=0.0,
                requires_nsfw_capable_model=False,
                reason_codes=[],
            )

        text = user_text.lower()
        reason_codes: list[str] = []

        mode_hint = _detect_mode(text)
        if self.router_log_reasons:
            if mode_hint == "persona":
                reason_codes.append("mode_persona_marker")
            elif mode_hint == "story":
                reason_codes.append("mode_story_marker")

        explicit_hits = _match_tokens(text, _EXPLICIT_NSFW_TOKENS)
        ambiguous_hits = _match_tokens(text, _AMBIGUOUS_NSFW_TOKENS)

        if explicit_hits:
            nsfw_score = 0.9
            if self.router_log_reasons:
                reason_codes.append("nsfw_explicit_signal")
        elif ambiguous_hits:
            nsfw_score = 0.55
            if self.router_log_reasons:
                reason_codes.append("nsfw_ambiguous_signal")
        else:
            nsfw_score = 0.05

        nsfw_required = nsfw_score >= self.nsfw_route_if_score_gte or (
            nsfw_score >= self.nsfw_uncertain_if_score_gte
            and mode_hint in {"persona", "story"}
            and self.persona_uncertain_routes_to_nsfw
        )

        if not self.router_log_reasons:
            reason_codes = []

        return InteractionHint(
            mode_hint=mode_hint,
            nsfw_score=nsfw_score,
            requires_nsfw_capable_model=nsfw_required,
            reason_codes=reason_codes,
        )


def _detect_mode(text: str) -> str:
    if _match_tokens(text, _PERSONA_MARKERS):
        return "persona"
    if _match_tokens(text, _STORY_MARKERS):
        return "story"
    return "general"


def _match_tokens(text: str, tokens: list[str]) -> list[str]:
    hits: list[str] = []
    for token in tokens:
        if token in text:
            hits.append(token)
    return hits


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip() not in {"0", "false", "False", "no"}


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
