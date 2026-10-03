"""Shared time utilities for the domain layer."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.domain.exceptions import ValidationError


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def require_utc(value: datetime, *, field: str) -> datetime:
    """Preserve an aware timestamp's instant; refuse ambiguous naive input."""
    if value.utcoffset() is None:
        raise ValidationError(f"{field} must include a UTC offset")
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{field} is outside the supported UTC range") from exc
