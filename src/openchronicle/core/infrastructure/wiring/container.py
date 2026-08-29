from __future__ import annotations

from typing import Any

from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.config.settings import (
    EmbeddingSettings,
    load_embedding_settings,
)
from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.errors.error_codes import CONFIG_ERROR
from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.config.config_loader import load_config_files
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _looks_private_host(url: str) -> bool:
    """Best-effort: does this endpoint look like it stays on the LAN?

    Used only to decide whether the content-egress WARNING fires, and
    deliberately fail-safe in the warning direction: anything ambiguous
    (a public-looking FQDN that happens to resolve locally) reads as
    remote and warns. Recognized as local: loopback, RFC1918/link-local
    literals, ``host.docker.internal``, ``*.local``/``*.internal``/
    ``*.lan``/``*.home``/``*.localhost`` suffixes, and dot-less
    single-label hostnames (LAN NetBIOS/mDNS names like ``your-nas``).
    """
    import ipaddress
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").strip("[]").lower()
    if not host:
        return False
    if host in ("localhost", "host.docker.internal"):
        return True
    try:
        return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if "." not in host:
        return True  # single-label LAN name
    return host.rsplit(".", 1)[-1] in ("local", "internal", "lan", "home", "localhost")


class CoreContainer:
    """Slim v3 DI container — memory storage + optional embeddings.

    Wires only what the v3 surface needs: SQLite-backed memory storage,
    optional embedding adapter for hybrid semantic + FTS5 search, and
    runtime paths. The v2 orchestrator/scheduler/LLM/router/webhook/asset/
    media/plugin/discord wiring is gone — those subsystems are archived
    on archive/openchronicle.v2.
    """

    def __init__(
        self,
        db_path: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        *,
        paths: RuntimePaths | None = None,
    ) -> None:
        if paths is None:
            paths = RuntimePaths.resolve(
                db_path=db_path,
                config_dir=config_dir,
                output_dir=output_dir,
            )
        self.paths = paths
        # Set by the db_integrity_check maintenance job; surfaced on both
        # health endpoints. A declared attribute (not setattr/getattr
        # conjuring) so mypy actually checks the four call sites.
        self.maintenance_degraded: bool = False

        db_path_resolved = paths.db_path
        config_dir_resolved = paths.config_dir
        output_dir_resolved = paths.output_dir

        db_path_resolved.parent.mkdir(parents=True, exist_ok=True)
        if not config_dir_resolved.exists():
            raise ConfigError(
                f"Config directory not found: {config_dir_resolved}. Run `oc init` or create the directory.",
                code=CONFIG_ERROR,
            )
        output_dir_resolved.mkdir(parents=True, exist_ok=True)

        file_configs = load_config_files(config_dir_resolved)

        self.storage = SqliteStore(db_path=str(db_path_resolved))
        self.storage.init_schema()
        try:
            self.embedding_settings = load_embedding_settings(file_configs.get("embedding"))
            self.embedding_port: EmbeddingPort | None = self._build_embedding_port()
            self.embedding_service: EmbeddingService | None = (
                EmbeddingService(self.embedding_port, self.storage) if self.embedding_port is not None else None
            )

            self.file_configs = file_configs
            self.config_dir = str(self.paths.config_dir)
        except BaseException:
            self.storage.close()
            raise

    def close(self) -> None:
        """Close managed resources."""
        self.storage.close()

    def __enter__(self) -> CoreContainer:
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        self.close()

    def embedding_status_dict(self) -> dict[str, Any]:
        """Return embedding subsystem status for health/diagnostics."""
        settings = self.embedding_settings
        if settings.provider == "none":
            return {"status": "disabled", "provider": "none"}
        if self.embedding_service is None:
            return {
                "status": "failed",
                "provider": settings.provider,
                "message": "Adapter failed to initialize — FTS5-only fallback active",
            }
        port = self.embedding_service.port
        coverage = self.embedding_service.embedding_status()
        # Provider degradation covers EVERY operation since 2026-08-28:
        # `failure_count` (with `last_failure_op`) counts consecutive
        # failures across search, save, and backfill, and drives the
        # status — a dead provider used to read "active" until someone
        # searched, while saves and backfill failed silently. The
        # original search-only counter keeps its keys for continuity.
        search_failures = self.embedding_service.search_failure_count
        failure_count = self.embedding_service.failure_count
        status = "degraded" if failure_count else "active"
        return {
            "status": status,
            "provider": settings.provider,
            "model": port.model_name(),
            # Three dimension facts, deliberately separate (0003 F2):
            # the operator's request, the adapter's claim, and what the
            # store actually holds — the old single field let health
            # display 768 while every stored row measured 384.
            "dimensions": port.dimensions(),
            "configured_dimensions": settings.dimensions,
            "stored_dimensions": self.storage.stored_embedding_dimensions(),
            "model_revision": port.model_revision(),
            "timeout_seconds": settings.timeout,
            "failure_count": failure_count,
            "last_failure_at": self.embedding_service.last_failure_at,
            "last_failure_op": self.embedding_service.last_failure_op,
            "search_failure_count": search_failures,
            "last_search_failure_at": self.embedding_service.last_search_failure_at,
            # The operator's egress choice, visible where agents look
            # (operator-directed 2026-08-29): "remote" means memory
            # content leaves this host on every save/semantic search.
            "content_egress": "remote" if self.embedding_endpoint_is_remote() else "local",
            **coverage,
        }

    def _embedding_endpoint(self) -> str:
        """The URL the active embedding provider actually talks to.

        Resolved from the same inputs the adapters read (settings + the
        provider env vars, empty-string = unset) — the composition root
        owns config, so this mirrors adapter resolution rather than
        reaching into adapter privates. Keep in lockstep with
        `openai_adapter` / `ollama_adapter` defaults.
        """
        import os

        provider = self.embedding_settings.provider
        if provider == "openai":
            return os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        if provider == "ollama":
            return os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        return ""  # stub / none — no endpoint

    def embedding_endpoint_is_remote(self) -> bool:
        """True when embedding content leaves this host (best-effort).

        Fail-safe toward warning: an ambiguous host classifies as
        remote. `stub`/`none` are never remote.
        """
        endpoint = self._embedding_endpoint()
        return bool(endpoint) and not _looks_private_host(endpoint)

    def _build_embedding_port(self) -> EmbeddingPort | None:
        import logging

        log = logging.getLogger(__name__)
        settings: EmbeddingSettings = self.embedding_settings
        if settings.provider == "none":
            log.info("Embedding provider: none (disabled, FTS5-only search)")
            return None

        try:
            port = self._create_embedding_adapter(settings)
            log.info(
                "Embedding adapter initialized: provider=%s, model=%s, dimensions=%d, timeout=%.1fs",
                settings.provider,
                port.model_name(),
                port.dimensions(),
                settings.timeout,
            )
            # Content-egress notice (operator-directed 2026-08-29): a
            # cloud embedding provider sends every saved memory's FULL
            # CONTENT and every semantic search query off this host. The
            # choice is the operator's to make — this warning exists so
            # it is always a MADE choice, never a silent default. It is
            # a notice, not a control: the actual mitigation is a
            # LAN-local provider (ollama on a LAN host).
            if self.embedding_endpoint_is_remote():
                log.warning(
                    "Embedding provider %r sends memory content to a REMOTE endpoint (%s) on every "
                    "save, and search queries on every semantic search — content leaves this host. "
                    "If that is not intended, point OC_EMBEDDING_PROVIDER=ollama at a LAN host to "
                    "keep embedding local. See docs/design/0006-embedding-provider-review.md.",
                    settings.provider,
                    self._embedding_endpoint(),
                )
            return port
        except Exception as exc:
            log.warning(
                "Embedding adapter (%s) failed to initialize: %s — falling back to FTS5-only",
                settings.provider,
                exc,
            )
            return None

    def _create_embedding_adapter(self, settings: EmbeddingSettings) -> EmbeddingPort:
        if settings.provider == "stub":
            from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter

            return StubEmbeddingAdapter(dims=settings.dimensions or 384)

        if settings.provider == "openai":
            from openchronicle.core.infrastructure.embedding.openai_adapter import OpenAIEmbeddingAdapter

            kwargs: dict[str, object] = {}
            if settings.model:
                kwargs["model"] = settings.model
            if settings.dimensions:
                kwargs["dimensions"] = settings.dimensions
            if settings.api_key:
                kwargs["api_key"] = settings.api_key
            kwargs["timeout_seconds"] = settings.timeout
            return OpenAIEmbeddingAdapter(**kwargs)  # type: ignore[arg-type]

        if settings.provider == "ollama":
            from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

            kwargs_o: dict[str, object] = {}
            if settings.model:
                kwargs_o["model"] = settings.model
            if settings.dimensions:
                kwargs_o["dimensions"] = settings.dimensions
            kwargs_o["timeout_seconds"] = settings.timeout
            return OllamaEmbeddingAdapter(**kwargs_o)  # type: ignore[arg-type]

        raise ConfigError(
            f"Unknown embedding provider: {settings.provider}. "
            "Set OC_EMBEDDING_PROVIDER to 'none', 'stub', 'openai', or 'ollama'.",
            code=CONFIG_ERROR,
        )
