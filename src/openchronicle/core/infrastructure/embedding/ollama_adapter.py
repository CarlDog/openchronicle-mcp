"""Ollama embedding adapter — truthful request contract (0003 Phase C).

The pre-Phase-C adapter accepted a ``dimensions`` config it never sent,
inherited Ollama's silent prefix truncation, trusted the response
blindly, and flattened structured errors to ``HTTP <status>``. Every
one of those is now explicit: the request carries the requested
dimensions (when configured) and ``truncate: false`` (an over-length
input fails visibly with Ollama's own actionable message instead of
embedding only a prefix — a partial representation must never
masquerade as full content), and the response is validated at the
boundary before anything is normalized or stored.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import httpx

from openchronicle.core.domain.embedding_fingerprint import settings_fingerprint
from openchronicle.core.domain.errors.error_codes import (
    CONNECTION_ERROR,
    CONTENT_TOO_LONG,
    PROVIDER_ERROR,
    TIMEOUT,
)
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.domain.exceptions import RevisionUnknownError
from openchronicle.core.domain.models.revision_snapshot import UNKNOWN_REVISION, RevisionSnapshot
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.time_utils import utc_now
from openchronicle.core.infrastructure.embedding.response_validation import validate_embeddings
from openchronicle.core.infrastructure.embedding.vector_norm import normalize_unit

logger = logging.getLogger(__name__)

# Bound on how much of Ollama's structured error body reaches our error
# message: actionable ("input exceeds maximum context length") without
# letting an arbitrary upstream body flood logs.
_ERROR_BODY_LIMIT = 300

# The /api/tags revision probe (ADR 0005 §7). httpx applies a timeout per
# phase, so this is 2 s to connect plus 3 s to read: about 5 s at worst.
_PROBE_TIMEOUT = httpx.Timeout(3.0, connect=2.0)
# A caller that finds a probe in flight waits a little longer than that
# probe can take, then uses whatever it produced.
_PROBE_WAIT_SECONDS = 6.0
# After a failed probe, a non-forced refresh (a write resolving an unknown
# revision) waits this long before probing again. A successful embed ends
# the wait early, since the server has just answered.
PROBE_COOLDOWN_SECONDS = 30.0
# While a revision is known, a failed probe changes nothing, so only this
# many in a row warn, repeated at most hourly. While it is unknown every
# write is refused, so the first failure warns, repeated every 15 minutes.
_KNOWN_FAILURES_BEFORE_WARNING = 3
_KNOWN_REMINDER_SECONDS = 3600.0
_UNKNOWN_REMINDER_SECONDS = 900.0


class OllamaEmbeddingAdapter(EmbeddingPort):
    """Embedding adapter using Ollama's ``/api/embed`` endpoint.

    ``dimensions=None`` (the default) means "whatever the model natively
    produces" — nothing is requested and the actual vector length is
    recorded as fact downstream. A configured value is SENT with the
    request and the response is validated against it; Ollama reduces and
    renormalizes for smaller values but silently ignores larger ones,
    which is exactly why request and validation travel together.
    """

    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        dimensions: int | None = None,
        host: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self._requested_dimensions = dimensions
        raw_host = host or os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self._host = _normalize_host(raw_host)
        # TLS verification for https hosts. Default ON; OLLAMA_VERIFY_TLS=0
        # (or false/no/off) disables it for LAN self-signed certs — the
        # same knob shape the fleet's Portainer client uses. Local
        # connections are first-class over BOTH http and https
        # (operator-directed 2026-08-29): the scheme comes from the host
        # URL, and this switch is what makes a self-signed LAN https
        # endpoint actually usable.
        self._verify_tls = os.getenv("OLLAMA_VERIFY_TLS", "").strip().lower() not in ("0", "false", "no", "off")
        if not self._verify_tls:
            logger.warning("OLLAMA_VERIFY_TLS disabled — TLS certificates for %s will not be verified", self._host)
        self._timeout = timeout_seconds
        # The model revision (ADR 0005 §7). It starts unknown, and only a
        # probe that finds the model in /api/tags sets it. Replaced whole,
        # never mutated, so a reader never sees a torn value.
        self._revision: RevisionSnapshot = UNKNOWN_REVISION
        self._probe_lock = threading.Lock()
        self._probe_failures = 0
        self._last_probe_failure: float | None = None  # time.monotonic()
        self._last_probe_warning: float | None = None  # time.monotonic()

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            # No provider round-trip (and no model load) for an empty batch.
            return []
        url = f"{self._host.rstrip('/')}/api/embed"
        body: dict[str, Any] = {
            "model": self._model,
            "input": texts,
            # Fail-visible, never a silent prefix embedding. The memory
            # and its FTS5 row are unaffected by a refusal; the vector
            # stays a backfill candidate.
            "truncate": False,
        }
        if self._requested_dimensions is not None:
            body["dimensions"] = self._requested_dimensions
        try:
            response = httpx.post(url, json=body, timeout=self._timeout, verify=self._verify_tls)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            # The old adapter checked none of this; its test suite even
            # pinned a 3-element vector as acceptable from a "768-dim" adapter.
            validate_embeddings(
                embeddings,
                expected=len(texts),
                provider="ollama",
                label="Ollama",
                model=self._model,
                requested_dimensions=self._requested_dimensions,
                dimensions_hint=" — values above the model's native length are silently ignored by Ollama",
            )
            # The server just answered, so a failed revision probe's
            # cooldown no longer applies: the next write may re-probe.
            self._last_probe_failure = None
            return [normalize_unit(vec) for vec in embeddings]
        except httpx.HTTPStatusError as exc:
            # The one structured place both status and body still exist —
            # classification happens here or not at all (ADR 0009).
            message = _upstream_error(exc.response)
            code = (
                CONTENT_TOO_LONG if _is_context_length_rejection(exc.response.status_code, message) else PROVIDER_ERROR
            )
            raise LLMProviderError(
                f"Ollama embedding failed: HTTP {exc.response.status_code}: {message}",
                error_code=code,
                details={"provider": "ollama", "model": self._model},
            ) from exc
        except httpx.ConnectError as exc:
            # Connection-refused is not a timeout — reporting it as one
            # sent operators chasing latency when the service was down.
            raise LLMProviderError(
                f"Ollama connection failed: {type(exc).__name__}: {exc}",
                error_code=CONNECTION_ERROR,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Ollama request timed out: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
            ) from exc

    def dimensions(self) -> int:
        # The requested value when configured; otherwise the common
        # default for the default model — a CLAIM for display. The
        # stored `dimensions` column always records the measured length.
        return self._requested_dimensions if self._requested_dimensions is not None else 768

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "ollama"

    @property
    def tracks_revision(self) -> bool:
        # A tag can be re-pulled with different weights under the same name.
        return True

    def revision_snapshot(self) -> RevisionSnapshot:
        return self._revision

    def model_revision(self) -> str | None:
        """The verified manifest digest, or None for a model listed without one.

        Raises ``RevisionUnknownError`` until a probe has found the model:
        returning None before that would claim "no revision" (ADR 0005 §7,
        design 0014 §1.1). Never probes; ``refresh_revision()`` does.
        """
        snapshot = self._revision
        if not snapshot.known:
            raise RevisionUnknownError(
                f"the revision of Ollama model {self._model!r} has not been verified",
                details={"provider": "ollama", "model": self._model},
            )
        return snapshot.value

    def refresh_revision(self, *, force: bool = False) -> RevisionSnapshot:
        """Probe ``/api/tags`` and return the resulting snapshot.

        Probes are serialized. A caller that finds one in flight waits for
        it, and then (unless forced) takes its result rather than probing
        again. Without ``force`` there is no probe once the revision is
        known, nor within ``PROBE_COOLDOWN_SECONDS`` of a failed probe.
        """
        if not self._probe_lock.acquire(timeout=_PROBE_WAIT_SECONDS):
            return self._revision
        try:
            if not force and (self._revision.known or self._in_cooldown()):
                return self._revision
            return self._probe()
        finally:
            self._probe_lock.release()

    def _in_cooldown(self) -> bool:
        failed_at = self._last_probe_failure
        return failed_at is not None and time.monotonic() - failed_at < PROBE_COOLDOWN_SECONDS

    def _probe(self) -> RevisionSnapshot:
        url = f"{self._host.rstrip('/')}/api/tags"
        try:
            response = httpx.get(url, timeout=_PROBE_TIMEOUT, verify=self._verify_tls)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return self._probe_failed(f"{type(exc).__name__}: {exc}")
        found = _find_model(payload, self._model)
        if found is None:
            return self._probe_failed("/api/tags returned no models list")
        listed, digest, names = found
        if not listed:
            logger.debug("Ollama /api/tags listed: %s", ", ".join(names) or "(nothing)")
            return self._probe_failed(f"model {self._model!r} is not among the {len(names)} model(s) /api/tags listed")
        return self._probe_succeeded(digest)

    def _probe_succeeded(self, digest: str | None) -> RevisionSnapshot:
        previous, failures = self._revision, self._probe_failures
        self._revision = RevisionSnapshot(known=True, value=digest, verified_at=utc_now())
        self._probe_failures = 0
        self._last_probe_failure = None
        self._last_probe_warning = None
        if previous.known and previous.value != digest:
            logger.warning(
                "Ollama model %s changed revision %s -> %s; vectors stamped with the old revision are stale "
                "and will be re-embedded",
                self._model,
                previous.value,
                digest,
            )
        elif not previous.known:
            logger.info("Ollama model %s revision verified: %s", self._model, digest or "none listed")
        elif failures:
            logger.info("Ollama model %s revision verified again after %d failed probe(s)", self._model, failures)
        return self._revision

    def _probe_failed(self, reason: str) -> RevisionSnapshot:
        """Record a failed probe. It never changes a verified revision.

        Warned once, then reminded: while unknown every write is refused, so
        that is loud at once; while known the value stays usable, so only a
        run of failures (re-pull detection is off meanwhile) warns.
        """
        now = time.monotonic()
        self._probe_failures += 1
        self._last_probe_failure = now
        since_warning = None if self._last_probe_warning is None else now - self._last_probe_warning
        if self._revision.known:
            due = self._probe_failures >= _KNOWN_FAILURES_BEFORE_WARNING and (
                since_warning is None or since_warning >= _KNOWN_REMINDER_SECONDS
            )
            message = "Ollama revision probe failed (%s); keeping the last verified revision of %s (%d in a row)"
        else:
            due = since_warning is None or since_warning >= _UNKNOWN_REMINDER_SECONDS
            message = (
                "Ollama revision probe failed (%s); the revision of %s is unverified, so no embeddings "
                "are written until it is (%d in a row)"
            )
        if due:
            self._last_probe_warning = now
            logger.warning(message, reason, self._model, self._probe_failures)
        else:
            logger.debug(message, reason, self._model, self._probe_failures)
        return self._revision

    def settings_fingerprint(self) -> str:
        return settings_fingerprint(
            {
                "dimensions": self._requested_dimensions,
                "truncate": False,
            }
        )


def _normalize_host(raw: str) -> str:
    """Give a scheme-less host value a scheme instead of a broken URL.

    ``OLLAMA_HOST=carldog-nas:11434`` used to produce
    ``carldog-nas:11434/api/embed`` — not a URL — and fail with an
    httpx error pointing nowhere near the cause. A value without
    ``://`` gets ``http://`` (Ollama's own client does the same);
    ``https://`` is passed through untouched — both schemes are
    first-class for local and remote hosts alike.
    """
    raw = raw.strip().rstrip("/")
    if "://" not in raw:
        return f"http://{raw}"
    return raw


def _is_context_length_rejection(status_code: int, message: str) -> bool:
    """Is this upstream rejection Ollama's over-length refusal? (ADR 0009)

    True only for a 400 whose error message contains ``context length``,
    case-insensitively — ground truth is the repo's captured rejection,
    ``"input exceeds maximum context length"`` (pinned in
    ``tests/test_embedding_adapters.py``). Conservative by design: the
    misclassification bias is asymmetric — a false negative preserves
    today's retry behavior, a false positive parks a row until its next
    content edit or space change — so nothing outside a 400 with that
    phrase classifies.
    """
    return status_code == 400 and "context length" in message.lower()


def _upstream_error(response: httpx.Response) -> str:
    """Ollama's structured ``{"error": ...}`` body, bounded and safe.

    "input exceeds maximum context length" is actionable; the old
    ``HTTP 400`` was not. Bounded so an arbitrary upstream body cannot
    flood a log line; falls back to a snippet of raw text when the body
    isn't the documented shape.
    """
    try:
        payload = response.json()
        message = payload.get("error") if isinstance(payload, dict) else None
    except Exception:
        message = None
    if not isinstance(message, str) or not message:
        message = response.text or "(no error body)"
    return message[:_ERROR_BODY_LIMIT]


def _canonical_model_name(name: str) -> str:
    """A model name as Ollama resolves it, so config and /api/tags compare equal.

    Ollama fills in a default registry (``registry.ollama.ai``), namespace
    (``library``) and tag (``latest``), and compares names
    case-insensitively.
    """
    name = name.strip().casefold()
    name = name.removeprefix("registry.ollama.ai/").removeprefix("library/")
    if ":" not in name.rsplit("/", 1)[-1]:
        name += ":latest"
    return name


def _find_model(payload: object, model: str) -> tuple[bool, str | None, list[str]] | None:
    """Look ``model`` up in an ``/api/tags`` body: (listed, digest, names).

    None for a body without a ``models`` list. A model listed with a
    missing or empty digest genuinely has no revision. An ABSENT model is
    not evidence of that: Ollama answers 200 while skipping a model it
    cannot read, and taking that as "none" re-embedded the corpus twice
    (design 0014 §1.1).
    """
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None
    wanted = _canonical_model_name(model)
    names: list[str] = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        entry_names = [n for n in (entry.get("name"), entry.get("model")) if isinstance(n, str) and n]
        names.extend(entry_names[:1])
        if any(_canonical_model_name(n) == wanted for n in entry_names):
            digest = entry.get("digest")
            return True, (digest if isinstance(digest, str) and digest else None), names
    return False, None, names
