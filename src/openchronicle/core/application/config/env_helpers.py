"""Consolidated environment variable and config value parsing helpers.

These helpers handle three-layer precedence: dataclass defaults -> JSON file
values -> env var overrides. They work with both string values (from env vars)
and native JSON types (bool, int, float) from config files.
"""

from __future__ import annotations

import logging
import os

_logger = logging.getLogger(__name__)


def parse_int(value: object, *, default: int) -> int:
    """Parse an integer from string, native int, or None.

    Native ints pass through. Strings are stripped and converted.
    Invalid values return default. None returns default.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        # bool is a subclass of int in Python — reject it
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        try:
            return int(raw)
        except ValueError:
            return default
    return default


def parse_float(value: object, *, default: float) -> float:
    """Parse a float from string, native float/int, or None.

    Native floats/ints pass through. Strings are stripped and converted.
    Invalid values return default. None returns default.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        try:
            return float(raw)
        except ValueError:
            return default
    return default


def parse_str(value: object, *, default: str) -> str:
    """Parse a string value, returning default for None or empty."""
    if value is None:
        return default
    if isinstance(value, str):
        return value if value else default
    return str(value)


def parse_int_env(raw: str | None, *, default: int, name: str) -> int:
    """``parse_int`` for env values, logging when a set value is discarded.

    One stale Portainer stack value must degrade to the default with a
    warning — never crash the config path, which under
    ``restart: unless-stopped`` turns a typo into an indefinite
    crash-loop (the trap the 2026-07-12 embedding fail-soft fixed for
    its own settings; this is the shared helper for everything else).
    """
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        _logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default


def resolve_port(*, env_name: str, env_raw: str | None, file_key: str, file_value: object, default: int) -> int:
    """The port a listener binds: ``env_name``, else core.json ``file_key``, else ``default``.

    Each source must be a whole number in 1-65535 (``bool`` is refused, as
    it is an ``int`` subclass). A bad value is logged with the source it came
    from (the env var, or the core.json key such as ``api.port``) and the
    port actually used, and never raises: under ``restart: unless-stopped``
    one bad value would otherwise crash-loop the service (QUAL-23). The env
    var is resolved first, so a bad core.json value that a valid env var
    overrides is reported as ignored, not as a fallback that never happened.
    """
    fallback = default
    file_bad = False
    if file_value is not None:
        if isinstance(file_value, int) and not isinstance(file_value, bool) and 1 <= file_value <= 65535:
            fallback = file_value
        else:
            file_bad = True

    env_text = env_raw.strip() if env_raw is not None else ""
    env_port: int | None = None
    if env_text:
        try:
            env_port = int(env_text)
        except ValueError:
            env_port = None
    if env_port is not None and 1 <= env_port <= 65535:
        if file_bad:
            _logger.warning(
                "Invalid core.json %s %r (must be 1-65535); ignored, %s=%d is set",
                file_key,
                file_value,
                env_name,
                env_port,
            )
        return env_port

    if file_bad:
        _logger.warning("Invalid core.json %s %r (must be 1-65535); using %d", file_key, file_value, fallback)
    if env_text:
        _logger.warning("Invalid %s=%r (must be 1-65535); using %d", env_name, env_text, fallback)
    return fallback


_TRUE_WORDS = frozenset({"1", "true", "yes", "on"})
_FALSE_WORDS = frozenset({"0", "false", "no", "off"})


def parse_bool_env(raw: str | None, *, default: bool, name: str, level: int = logging.WARNING) -> bool:
    """A yes/no env value: the one parser for every boolean switch.

    Unset or blank (compose's ``${VAR:-}`` injects ``""``) is the default.
    ``1``/``true``/``yes``/``on`` and ``0``/``false``/``no``/``off`` are
    recognized, case-insensitively. Anything else is logged, naming the
    variable, and falls back to the default rather than to a guess: a typo
    must never silently flip a switch away from its safe setting, and must
    never stop startup either.
    """
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE_WORDS:
        return True
    if value in _FALSE_WORDS:
        return False
    _logger.log(level, "Invalid %s=%r (expected true or false); using the default, %s", name, raw, default)
    return default


def env_override(env_name: str, file_value: object) -> object:
    """Return env var if set to a non-empty value, otherwise file_value.

    This implements the precedence: env var > JSON file > (caller's default).
    An empty (or whitespace-only) env var counts as UNSET: MCP hosts and
    docker-compose ``${VAR:-}`` substitutions inject "" for every blank
    field, so letting "" win would silently shadow the file value — seen
    live as core.json embedding config being ignored under the NAS compose
    file. Same empty-means-unset convention as the api_key and
    allowed-hosts boundaries.
    """
    env_val = os.getenv(env_name)
    if env_val is not None and env_val.strip():
        return env_val
    return file_value


def parse_csv_tags(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a list of stripped, non-empty tags.

    Returns None if the input is None or empty, which signals "no filter"
    in search contexts.
    """
    if not value:
        return None
    return [t.strip() for t in value.split(",") if t.strip()]
