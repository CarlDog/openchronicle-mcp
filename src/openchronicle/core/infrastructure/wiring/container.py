from __future__ import annotations

import os
from typing import Any

from openchronicle.core.application.config.budget_config import load_budget_policy
from openchronicle.core.application.config.env_helpers import env_override, parse_int
from openchronicle.core.application.config.model_config import ModelConfigLoader
from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.config.settings import (
    load_conversation_settings,
    load_moe_settings,
    load_privacy_outbound_settings,
    load_router_assist_settings,
    load_telemetry_settings,
)
from openchronicle.core.application.policies.rate_limiter import RateLimitConfig, RateLimiter
from openchronicle.core.application.policies.retry_policy import RetryConfig, RetryPolicy
from openchronicle.core.application.routing.pool_config import load_pool_config
from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.runtime.plugin_loader import PluginLoader
from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.application.services.asset_storage import AssetFileStorage
from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.services.scheduler import SchedulerService
from openchronicle.core.application.services.webhook_dispatcher import WebhookDispatcher
from openchronicle.core.application.services.webhook_service import WebhookService
from openchronicle.core.domain.errors.error_codes import CONFIG_ERROR
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError
from openchronicle.core.domain.ports.router_assist_port import RouterAssistPort
from openchronicle.core.infrastructure.config.config_loader import load_config_files, load_plugin_config
from openchronicle.core.infrastructure.llm.provider_facade import create_provider_aware_llm
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.privacy.rule_privacy import RulePrivacyGate
from openchronicle.core.infrastructure.router_assist import LinearRouterAssist, OnnxRouterAssist
from openchronicle.core.infrastructure.routing.hybrid_router import HybridInteractionRouter
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


class CoreContainer:
    def __init__(
        self,
        db_path: str | None = None,
        config_dir: str | None = None,
        plugin_dir: str | None = None,
        output_dir: str | None = None,
        llm: LLMPort | None = None,
        *,
        paths: RuntimePaths | None = None,
    ) -> None:
        # Resolve all data paths through RuntimePaths (four-layer precedence).
        # Individual string params feed into RuntimePaths.resolve() when paths is None.
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
        plugin_dir_resolved = paths.plugin_dir
        output_dir_resolved = paths.output_dir

        db_path_resolved.parent.mkdir(parents=True, exist_ok=True)
        if not config_dir_resolved.exists():
            raise LLMProviderError(
                f"Config directory not found: {config_dir_resolved}",
                error_code=CONFIG_ERROR,
                hint="Run `oc init` or create the directory.",
                details={"config_dir": str(config_dir_resolved)},
            )
        plugin_dir_resolved.mkdir(parents=True, exist_ok=True)
        output_dir_resolved.mkdir(parents=True, exist_ok=True)

        # Load core.json config file
        file_configs = load_config_files(config_dir_resolved)

        self.storage = SqliteStore(db_path=str(db_path_resolved))
        self.storage.init_schema()
        try:
            self.event_logger = EventLogger(self.storage)
            self.privacy_gate = RulePrivacyGate()
            self.privacy_settings = load_privacy_outbound_settings(file_configs.get("privacy"))
            self.telemetry_settings = load_telemetry_settings(file_configs.get("telemetry"))
            self.conversation_settings = load_conversation_settings(file_configs.get("conversation"))
            self.moe_settings = load_moe_settings(file_configs.get("moe"))
            self.budget_policy = load_budget_policy(file_configs.get("budget"))

            router_fc = file_configs.get("router")
            router_assist_settings = load_router_assist_settings(
                router_fc.get("assist") if isinstance(router_fc, dict) else None
            )

            # Shared model config loader (used by LLM facade and router policy)
            self.model_config_loader = ModelConfigLoader(str(config_dir_resolved))

            # Use provider-aware facade if no explicit LLM provided
            if llm is None:
                llm = create_provider_aware_llm(
                    config_dir=str(config_dir_resolved),
                    model_config_loader=self.model_config_loader,
                )

            self.llm = llm

            assist: RouterAssistPort | None = None
            if router_assist_settings.enabled:
                if not router_assist_settings.model_path:
                    raise LLMProviderError(
                        "Router assist model path not configured",
                        error_code=CONFIG_ERROR,
                        hint="Set OC_ROUTER_ASSIST_MODEL_PATH to a model JSON file.",
                    )
                backend = router_assist_settings.backend.lower()
                if backend == "linear":
                    assist = LinearRouterAssist(
                        model_path=router_assist_settings.model_path,
                        timeout_ms=router_assist_settings.timeout_ms,
                    )
                elif backend == "onnx":
                    assist = OnnxRouterAssist(
                        model_path=router_assist_settings.model_path,
                        timeout_ms=router_assist_settings.timeout_ms,
                    )
                else:
                    raise LLMProviderError(
                        f"Unsupported router assist backend: {router_assist_settings.backend}",
                        error_code=CONFIG_ERROR,
                        hint="Set OC_ROUTER_ASSIST_BACKEND to 'linear' or 'onnx'.",
                    )

            self.interaction_router = HybridInteractionRouter(
                base_router=RuleInteractionRouter(file_config=router_fc),
                assist=assist,
            )

            # Build pool config + router policy from core.json (top-level keys)
            pool_config = load_pool_config(file_configs)
            router_policy = RouterPolicy(
                file_config=file_configs,
                pool_config=pool_config,
                model_config_loader=self.model_config_loader,
            )
            self.router_policy = router_policy

            # Build rate limiter — per-model rate limits live in model configs.
            # Global rate limiter only respects env var overrides as system-wide ceiling.
            retry_fc = file_configs.get("retry", {}) if isinstance(file_configs.get("retry"), dict) else {}
            max_wait_raw = env_override("OC_LLM_MAX_WAIT_MS", retry_fc.get("rate_limit_max_wait_ms"))

            rate_config = RateLimitConfig(
                rpm_limit=parse_int(os.getenv("OC_LLM_RPM_LIMIT"), default=0) or None,
                tpm_limit=parse_int(os.getenv("OC_LLM_TPM_LIMIT"), default=0) or None,
                max_wait_ms=parse_int(max_wait_raw, default=5000),
            )
            rate_limiter = RateLimiter(rate_config)

            max_retries_raw = env_override("OC_LLM_MAX_RETRIES", retry_fc.get("max_retries"))
            max_retry_sleep_raw = env_override("OC_LLM_MAX_RETRY_SLEEP_MS", retry_fc.get("max_retry_sleep_ms"))

            retry_config = RetryConfig(
                max_retries=parse_int(max_retries_raw, default=2),
                max_retry_sleep_ms=parse_int(max_retry_sleep_raw, default=2000),
            )
            retry_policy = RetryPolicy(retry_config)

            self.handler_registry = TaskHandlerRegistry()
            self.plugin_loader = PluginLoader(
                plugins_dir=str(plugin_dir_resolved),
                handler_registry=self.handler_registry,
                config_loader=load_plugin_config,
            )
            self.plugin_loader.load_plugins()
            self.orchestrator = OrchestratorService(
                storage=self.storage,
                llm=self.llm,
                plugins=self.plugin_loader.registry_instance(),
                handler_registry=self.plugin_loader.handler_registry_instance(),
                emit_event=self.event_logger.append,
                rate_limiter=rate_limiter,
                retry_policy=retry_policy,
                router=router_policy,
            )
            self.scheduler = SchedulerService(
                storage=self.storage,
                submit_task=self.orchestrator.submit_task,
                emit_event=self.event_logger.append,
            )

            self.asset_file_storage = AssetFileStorage(base_dir=str(self.paths.assets_dir))

            # Embedding service (optional — hybrid memory search)
            self.embedding_port: EmbeddingPort | None = self._build_embedding_port()
            self.embedding_service: EmbeddingService | None = (
                EmbeddingService(self.embedding_port, self.storage) if self.embedding_port is not None else None
            )

            # Webhook service + dispatcher (composite emit_event)
            self.webhook_service = WebhookService(store=self.storage)
            self.webhook_dispatcher: WebhookDispatcher | None = None
            # Check if any webhooks exist at startup; dispatcher starts lazily
            if self.storage.list_subscriptions(active_only=True):
                self.webhook_dispatcher = WebhookDispatcher(webhook_service=self.webhook_service, store=self.storage)
                self.webhook_dispatcher.start()

            # Store for config show and diagnostics
            self.file_configs = file_configs
            self.config_dir = str(self.paths.config_dir)
        except BaseException:
            self.storage.close()
            raise

    def emit_event(self, event: Event) -> None:
        """Composite event emitter: log + dispatch to webhooks."""
        self.event_logger.append(event)
        if self.webhook_dispatcher is not None:
            self.webhook_dispatcher.enqueue(event)

    def ensure_webhook_dispatcher(self) -> WebhookDispatcher:
        """Lazily create and start the webhook dispatcher."""
        if self.webhook_dispatcher is None:
            self.webhook_dispatcher = WebhookDispatcher(webhook_service=self.webhook_service, store=self.storage)
            self.webhook_dispatcher.start()
        return self.webhook_dispatcher

    def close(self) -> None:
        """Close managed resources (storage connection, webhook dispatcher)."""
        if self.webhook_dispatcher is not None:
            self.webhook_dispatcher.stop()
        self.storage.close()

    def __enter__(self) -> CoreContainer:
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        self.close()

    def as_dict(self) -> dict[str, Any]:
        return {
            "storage": self.storage,
            "event_logger": self.event_logger,
            "privacy_gate": self.privacy_gate,
            "privacy_settings": self.privacy_settings,
            "llm": self.llm,
            "interaction_router": self.interaction_router,
            "plugins": self.plugin_loader.registry_instance(),
            "handler_registry": self.plugin_loader.handler_registry_instance(),
            "orchestrator": self.orchestrator,
            "scheduler": self.scheduler,
        }

    def _build_embedding_port(self) -> EmbeddingPort | None:
        """Build embedding port based on OC_EMBEDDING_PROVIDER env var."""
        provider = os.getenv("OC_EMBEDDING_PROVIDER", "none").lower()
        if provider == "none":
            return None

        model = os.getenv("OC_EMBEDDING_MODEL")
        dims_raw = os.getenv("OC_EMBEDDING_DIMENSIONS")
        dims = int(dims_raw) if dims_raw else None

        if provider == "stub":
            from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter

            return StubEmbeddingAdapter(dims=dims or 384)

        if provider == "openai":
            from openchronicle.core.infrastructure.embedding.openai_adapter import OpenAIEmbeddingAdapter

            kwargs: dict[str, object] = {}
            if model:
                kwargs["model"] = model
            if dims:
                kwargs["dimensions"] = dims
            return OpenAIEmbeddingAdapter(**kwargs)  # type: ignore[arg-type]

        if provider == "ollama":
            from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

            kwargs_o: dict[str, object] = {}
            if model:
                kwargs_o["model"] = model
            if dims:
                kwargs_o["dimensions"] = dims
            return OllamaEmbeddingAdapter(**kwargs_o)  # type: ignore[arg-type]

        raise LLMProviderError(
            f"Unknown embedding provider: {provider}",
            error_code=CONFIG_ERROR,
            hint="Set OC_EMBEDDING_PROVIDER to 'none', 'stub', 'openai', or 'ollama'.",
        )
