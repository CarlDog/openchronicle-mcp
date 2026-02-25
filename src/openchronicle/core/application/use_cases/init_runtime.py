from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openchronicle.core.application.config.paths import RuntimePaths


def resolve_runtime_paths() -> RuntimePaths:
    """Convenience wrapper — delegates to RuntimePaths.resolve()."""
    return RuntimePaths.resolve()


def execute(
    paths: RuntimePaths,
    *,
    write_templates: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    paths_result = {
        "db_path": _ensure_parent(paths.db_path),
        "config_dir": _ensure_dir(paths.config_dir),
        "plugin_dir": _ensure_dir(paths.plugin_dir),
        "output_dir": _ensure_dir(paths.output_dir),
        "assets_dir": _ensure_dir(paths.assets_dir),
    }

    templates_result = {
        "model_config": {"path": str(paths.config_dir / "models" / "example_disabled.json"), "status": "skipped"},
        "router_assist_model": {
            "path": str(paths.config_dir / "router_assist_linear_model.json"),
            "status": "skipped",
        },
    }

    if write_templates:
        models_dir = paths.config_dir / "models"
        _ensure_dir(models_dir)

        model_payload = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "enabled": False,
            "display_name": "Example (disabled)",
            "api_config": {
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "default_base_url": "https://api.openai.com/v1",
                "timeout": 30,
                "auth_header": "Authorization",
                "auth_format": "Bearer {api_key}",
            },
        }
        templates_result["model_config"] = _write_template(
            models_dir / "example_disabled.json",
            json.dumps(model_payload, indent=2) + "\n",
            force=force,
        )

        assist_payload = {
            "version": "1",
            "bias": -2.0,
            "weights": {"nsfw": 3.0, "explicit": 2.5, "nude": 2.0, "adult": 1.5},
            "token_limit": 32,
        }
        templates_result["router_assist_model"] = _write_template(
            paths.config_dir / "router_assist_linear_model.json",
            json.dumps(assist_payload, indent=2) + "\n",
            force=force,
        )

    return {
        "status": "ok",
        "paths": paths_result,
        "templates": templates_result,
    }


def _ensure_parent(path: Path) -> dict[str, str]:
    parent = path.parent
    status = "exists" if parent.exists() else "created"
    parent.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(path),
        "parent": str(parent),
        "status": status,
    }


def _ensure_dir(path: Path) -> dict[str, str]:
    status = "exists" if path.exists() else "created"
    path.mkdir(parents=True, exist_ok=True)
    return {"path": str(path), "status": status}


def _write_template(path: Path, content: str, *, force: bool) -> dict[str, str]:
    if path.exists() and not force:
        return {"path": str(path), "status": "exists"}

    path.parent.mkdir(parents=True, exist_ok=True)
    status = "overwritten" if path.exists() else "created"
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "status": status}
