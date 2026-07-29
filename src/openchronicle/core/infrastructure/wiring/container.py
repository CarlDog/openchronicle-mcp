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
        plugin_dir: str | None = None,
        output_dir: str | None = None,
        *,
        paths: RuntimePaths | None = None,
    ) -> None:
        if paths is None:
            paths = RuntimePaths.resolve(
                db_path=db_path,
                config_dir=config_dir,
                plugin_dir=plugin_dir,
                output_dir=output_dir,
            )
        self.paths = paths

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
        # Search-time degradation: if the provider has been failing, the
        # service flips to FTS5-only and tracks a counter. Surface the
        # counter here so /api/v1/health can show it.
        failure_count = self.embedding_service.search_failure_count
        last_failure = self.embedding_service.last_failure_at
        status = "degraded" if failure_count else "active"
        return {
            "status": status,
            "provider": settings.provider,
            "model": port.model_name(),
            "dimensions": port.dimensions(),
            "timeout_seconds": settings.timeout,
            "search_failure_count": failure_count,
            "last_search_failure_at": last_failure,
            **coverage,
        }

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
