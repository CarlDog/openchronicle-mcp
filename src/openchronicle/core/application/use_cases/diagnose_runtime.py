"""Diagnose runtime use case for troubleshooting Docker/WSL/persistence issues."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport


def execute() -> DiagnosticsReport:
    """Collect runtime diagnostics without requiring orchestrator or container."""
    # 1. Resolve paths from environment (same source as CoreContainer)
    db_path = os.getenv("OC_DB_PATH", "data/openchronicle.db")
    config_dir = os.getenv("OC_CONFIG_DIR", "config")
    plugin_dir = os.getenv("OC_PLUGIN_DIR", "plugins")

    # 2. Filesystem checks
    db_path_obj = Path(db_path)
    config_dir_obj = Path(config_dir)
    plugin_dir_obj = Path(plugin_dir)

    db_exists = db_path_obj.exists()
    db_size_bytes: int | None = None
    db_modified_utc: datetime | None = None

    if db_exists:
        try:
            stat_info = db_path_obj.stat()
            db_size_bytes = stat_info.st_size
            db_modified_utc = datetime.utcfromtimestamp(stat_info.st_mtime)
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

    return DiagnosticsReport(
        timestamp_utc=datetime.utcnow(),
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
    if running_in_container_hint and db_path.startswith("/data"):
        return "DB configured for container volume at /data. If you expect a host file, ensure a bind-mount overlay is used."
    if "\\" in db_path or db_path[1:3] == ":\\" or (len(db_path) > 2 and db_path[1] == ":"):
        # Windows path detection (C:\\ or C:/)
        return "DB appears to be on a Windows bind-mount path."
    return "Persistence mode unknown."


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
