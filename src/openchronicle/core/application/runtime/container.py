from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openchronicle.core.application.policies.rate_limiter import RateLimitConfig, RateLimiter
from openchronicle.core.application.policies.retry_policy import RetryConfig, RetryPolicy
from openchronicle.core.application.routing.pool_config import load_pool_config
from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.runtime.plugin_loader import PluginLoader
from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.services.scheduler import SchedulerService
from openchronicle.core.domain.errors.error_codes import CONFIG_ERROR
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError
from openchronicle.core.domain.ports.router_assist_port import RouterAssistPort
from openchronicle.core.infrastructure.config.budget_config import load_budget_policy
from openchronicle.core.infrastructure.config.config_loader import load_config_files
from openchronicle.core.infrastructure.config.env_helpers import env_override, parse_int
from openchronicle.core.infrastructure.config.settings import (
    load_privacy_outbound_settings,
    load_router_assist_settings,
    load_telemetry_settings,
)
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
    ) -> None:
        db_path_str = db_path if db_path is not None else os.getenv("OC_DB_PATH", "data/openchronicle.db")
        config_dir_str = config_dir if config_dir is not None else os.getenv("OC_CONFIG_DIR", "config")
        plugin_dir_str = plugin_dir if plugin_dir is not None else os.getenv("OC_PLUGIN_DIR", "plugins")
        output_dir_str = output_dir if output_dir is not None else os.getenv("OC_OUTPUT_DIR", "output")

        db_path_resolved = Path(db_path_str)
        config_dir_resolved = Path(config_dir_str)
        plugin_dir_resolved = Path(plugin_dir_str)
        output_dir_resolved = Path(output_dir_str)

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
        self.event_logger = EventLogger(self.storage)
        self.privacy_gate = RulePrivacyGate()
        self.privacy_settings = load_privacy_outbound_settings(file_configs.get("privacy"))
        self.telemetry_settings = load_telemetry_settings(file_configs.get("telemetry"))
        self.budget_policy = load_budget_policy(file_configs.get("budget"))

        router_fc = file_configs.get("router")
        router_assist_settings = load_router_assist_settings(
            router_fc.get("assist") if isinstance(router_fc, dict) else None
        )

        # Use provider-aware facade if no explicit LLM provided
        if llm is None:
            llm = create_provider_aware_llm(config_dir=config_dir_str)

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
        )

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
            config_dir=str(config_dir_resolved),
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

        # Store for config show and diagnostics
        self.file_configs = file_configs
        self.config_dir = str(config_dir_resolved)

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
