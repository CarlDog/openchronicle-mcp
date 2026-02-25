"""Diagnose runtime use case for troubleshooting Docker/WSL/persistence issues."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport

_logger = logging.getLogger(__name__)


def execute() -> DiagnosticsReport:
    """Collect runtime diagnostics without requiring orchestrator or container."""
    # 1. Resolve paths from canonical RuntimePaths (four-layer precedence)
    paths = RuntimePaths.resolve()
    db_path = str(paths.db_path)
    config_dir = str(paths.config_dir)
    plugin_dir = str(paths.plugin_dir)

    # 2. Filesystem checks
    db_path_obj = paths.db_path
    config_dir_obj = paths.config_dir
    plugin_dir_obj = paths.plugin_dir

    db_exists = db_path_obj.exists()
    db_size_bytes: int | None = None
    db_modified_utc: datetime | None = None

    if db_exists:
        try:
            stat_info = db_path_obj.stat()
            db_size_bytes = stat_info.st_size
            db_modified_utc = datetime.fromtimestamp(stat_info.st_mtime, UTC)
        except (OSError, ValueError):
            pass

    config_dir_exists = config_dir_obj.exists()
    plugin_dir_exists = plugin_dir_obj.exists()

    # 3. Container hint (heuristic)
    running_in_container_hint = _detect_container()

    # 4. Persistence hint (heuristic)
    persistence_hint = _infer_persistence_hint(db_path, running_in_container_hint)

    # 5. Provider env summary (SAFE only)
    provider_env_summary = _build_provider_env_summary()

    # 6. Model config discovery (v1 configs from <OC_CONFIG_DIR>/models/*.json)
    models_dir = str(config_dir_obj / "models")
    models_dir_exists = (config_dir_obj / "models").exists()
    model_config_files_count = 0
    model_config_provider_summary: dict[str, dict[str, int]] = {}
    model_config_load_errors: dict[str, str] = {}

    if models_dir_exists:
        model_config_files_count, model_config_provider_summary, model_config_load_errors = _discover_model_configs(
            Path(models_dir)
        )

    return DiagnosticsReport(
        timestamp_utc=datetime.now(UTC),
        db_path=db_path,
        db_exists=db_exists,
        db_size_bytes=db_size_bytes,
        db_modified_utc=db_modified_utc,
        config_dir=config_dir,
        config_dir_exists=config_dir_exists,
        plugin_dir=plugin_dir,
        plugin_dir_exists=plugin_dir_exists,
        running_in_container_hint=running_in_container_hint,
        persistence_hint=persistence_hint,
        provider_env_summary=provider_env_summary,
        models_dir=models_dir,
        models_dir_exists=models_dir_exists,
        model_config_files_count=model_config_files_count,
        model_config_provider_summary=model_config_provider_summary,
        model_config_load_errors=model_config_load_errors,
    )


def _detect_container() -> bool:
    """Detect if running in a container (heuristic)."""
    # Check for /.dockerenv (most common Docker indicator)
    if Path("/.dockerenv").exists():
        return True
    # Check if db_path starts with /data (common container mount point)
    db_path = os.getenv("OC_DB_PATH", "data/openchronicle.db")
    return db_path.startswith("/data")


def _infer_persistence_hint(db_path: str, running_in_container_hint: bool) -> str:
    """Infer persistence mode from path and container hint."""
    # Normalize to forward slashes for cross-platform pattern matching
    db_posix = db_path.replace("\\", "/")
    if running_in_container_hint and db_posix.startswith("/data"):
        return "DB configured for container volume at /data. If you expect a host file, ensure a bind-mount overlay is used."
    if "\\" in db_path or db_path[1:3] == ":\\" or (len(db_path) > 2 and db_path[1] == ":"):
        # Windows path detection (C:\\ or C:/)
        return "DB appears to be on a Windows bind-mount path."
    return "Persistence mode unknown."


def _discover_model_configs(
    models_dir: Path,
) -> tuple[int, dict[str, dict[str, int]], dict[str, str]]:
    """
    Discover model configs in <OC_CONFIG_DIR>/models/*.json.

    Returns:
        (file_count, provider_summary, load_errors)

    provider_summary structure:
        {
            "provider_name": {
                "enabled_count": int,
                "disabled_count": int,
                "requires_api_key_count": int,
                "api_key_set_count": int,
                "api_key_missing_count": int,
            },
            ...
        }

    load_errors structure:
        {
            "filename": "error description (no content)",
            ...
        }

    Rules:
    - Never print api_key values
    - Report filenames for parse errors
    - Deterministic ordering (sort by filename)
    """
    file_count = 0
    provider_summary: dict[str, dict[str, int]] = {}
    load_errors: dict[str, str] = {}

    if not models_dir.exists():
        return 0, {}, {}

    for config_file in sorted(models_dir.glob("*.json"), key=lambda p: p.name.lower()):
        try:
            raw = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            load_errors[config_file.name] = f"Invalid JSON: {exc}"
            continue
        except (OSError, UnicodeDecodeError) as exc:
            load_errors[config_file.name] = f"Read error: {exc}"
            continue

        file_count += 1

        # Extract provider and model
        provider = raw.get("provider")
        model = raw.get("model") or raw.get("api_config", {}).get("model")

        if not provider or not model:
            load_errors[config_file.name] = "Missing required provider/model fields"
            continue

        provider = str(provider).lower()

        # Initialize provider entry if not present
        if provider not in provider_summary:
            provider_summary[provider] = {
                "enabled_count": 0,
                "disabled_count": 0,
                "requires_api_key_count": 0,
                "api_key_set_count": 0,
                "api_key_missing_count": 0,
            }

        # Check enabled status
        enabled = raw.get("enabled", True)
        if isinstance(enabled, bool):
            if enabled:
                provider_summary[provider]["enabled_count"] += 1
            else:
                provider_summary[provider]["disabled_count"] += 1
        else:
            provider_summary[provider]["enabled_count"] += 1

        # Skip api_key analysis for disabled configs
        if not (isinstance(enabled, bool) and enabled) and enabled is not True:
            continue

        # Analyze api_key configuration (enabled configs only)
        api_config = raw.get("api_config", {})
        if isinstance(api_config, dict):
            auth_format = api_config.get("auth_format")
            auth_header = api_config.get("auth_header")

            # Check if API key is required
            requires_key = False
            if isinstance(auth_format, str) and "{api_key}" in auth_format or auth_header:
                requires_key = True

            if requires_key:
                provider_summary[provider]["requires_api_key_count"] += 1

                # Check if API key is set (inline or via env)
                api_key_inline = api_config.get("api_key")
                api_key_is_set = bool(isinstance(api_key_inline, str) and api_key_inline.strip())

                if api_key_is_set:
                    provider_summary[provider]["api_key_set_count"] += 1
                else:
                    # Check env var
                    api_key_env_name = api_config.get("api_key_env")
                    if isinstance(api_key_env_name, str) and api_key_env_name.strip():
                        if os.getenv(api_key_env_name.strip()):
                            provider_summary[provider]["api_key_set_count"] += 1
                        else:
                            provider_summary[provider]["api_key_missing_count"] += 1
                    else:
                        # Check standard env mapping
                        standard_env = _standard_api_env(provider)
                        if standard_env and os.getenv(standard_env):
                            provider_summary[provider]["api_key_set_count"] += 1
                        else:
                            provider_summary[provider]["api_key_missing_count"] += 1

    return file_count, provider_summary, load_errors


def _standard_api_env(provider: str) -> str | None:
    """Map provider to standard API key environment variable."""
    mapping = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "ollama": None,  # Ollama doesn't require API key typically
    }
    return mapping.get(provider.lower())


def _build_provider_env_summary() -> dict[str, str]:
    """Build a safe provider environment summary without secrets."""
    summary: dict[str, str] = {}

    # OPENAI_API_KEY: only report if set/missing, never show value
    openai_key = os.getenv("OPENAI_API_KEY")
    summary["OPENAI_API_KEY"] = "set" if openai_key else "missing"

    # OLLAMA_HOST: safe to show if set (it's just a URL)
    ollama_host = os.getenv("OLLAMA_HOST")
    if ollama_host:
        summary["OLLAMA_HOST"] = ollama_host
    else:
        summary["OLLAMA_HOST"] = "missing"

    # OC_LLM_PROVIDER: show value if present
    llm_provider = os.getenv("OC_LLM_PROVIDER")
    if llm_provider:
        summary["OC_LLM_PROVIDER"] = llm_provider

    # OC_LLM_MODEL_FAST / OC_LLM_MODEL_QUALITY: show if present
    model_fast = os.getenv("OC_LLM_MODEL_FAST")
    if model_fast:
        summary["OC_LLM_MODEL_FAST"] = model_fast

    model_quality = os.getenv("OC_LLM_MODEL_QUALITY")
    if model_quality:
        summary["OC_LLM_MODEL_QUALITY"] = model_quality

    # OPENAI_MODEL: show if present
    openai_model = os.getenv("OPENAI_MODEL")
    if openai_model:
        summary["OPENAI_MODEL"] = openai_model

    # Budget/rate limits: these are operational config, safe to show
    rpm_limit = os.getenv("OC_LLM_RPM_LIMIT")
    if rpm_limit:
        summary["OC_LLM_RPM_LIMIT"] = rpm_limit

    tpm_limit = os.getenv("OC_LLM_TPM_LIMIT")
    if tpm_limit:
        summary["OC_LLM_TPM_LIMIT"] = tpm_limit

    return summary
