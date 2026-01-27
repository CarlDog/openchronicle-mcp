from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    ask_conversation,
    create_conversation,
    export_convo,
    remember_turn,
    run_task,
)
from openchronicle.core.domain.services.verification import VerificationService
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return current


@contextmanager
def _temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    original: dict[str, str | None] = {}
    for key, value in overrides.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, stored_value in original.items():
            if stored_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = stored_value


def _prepare_workspace(base_dir: Path) -> tuple[dict[str, Path], bool]:
    marker = base_dir / ".oc_selftest"
    data_dir = base_dir / "data"
    config_dir = base_dir / "config"
    plugins_dir = base_dir / "plugins"
    output_dir = base_dir / "output"
    cleanup_base_dir = False

    if base_dir.exists():
        marker_exists = marker.exists()
        if not marker_exists:
            existing = [p for p in (data_dir, config_dir, plugins_dir, output_dir) if p.exists()]
            if existing:
                raise ValueError(
                    "Selftest directory already contains OpenChronicle data but is missing .oc_selftest marker. "
                    "Use an empty directory or remove existing selftest data."
                )
        else:
            cleanup_base_dir = True
            for path in (data_dir, config_dir, plugins_dir, output_dir):
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
    else:
        base_dir.mkdir(parents=True, exist_ok=True)
        cleanup_base_dir = True

    marker.write_text("openchronicle-selftest\n", encoding="utf-8")

    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return (
        {
            "base_dir": base_dir,
            "data_dir": data_dir,
            "config_dir": config_dir,
            "plugins_dir": plugins_dir,
            "output_dir": output_dir,
        },
        cleanup_base_dir,
    )


def _copy_storytelling_plugin(target_plugins_dir: Path) -> None:
    candidates: list[Path] = []
    env_plugins_dir = os.getenv("OC_PLUGIN_DIR")
    if env_plugins_dir:
        candidates.append(Path(env_plugins_dir) / "storytelling")
    repo_root = _find_repo_root(Path(__file__))
    candidates.append(repo_root / "plugins" / "storytelling")
    candidates.append(Path("/app/plugins/storytelling"))

    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        raise FileNotFoundError("Storytelling plugin not found in repo plugins directory")

    destination = target_plugins_dir / "storytelling"
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def execute(
    base_dir: str,
    *,
    json_output: bool,
    keep_artifacts: bool,
    with_plugins: bool = True,
    telemetry_self_report: bool = False,
) -> dict[str, object]:
    base_path = Path(base_dir).resolve()
    workspace: dict[str, Path] | None = None
    cleanup_base_dir = False
    result: dict[str, object] = {
        "ok": False,
        "workspace": {
            "base_dir": str(base_path),
            "data_dir": str(base_path / "data"),
            "config_dir": str(base_path / "config"),
            "plugins_dir": str(base_path / "plugins"),
            "output_dir": str(base_path / "output"),
        },
        "conversation_id": None,
        "turn_id": None,
        "memory_ids": [],
        "export_path": None,
        "plugin_result": None,
        "failure": None,
        "json_output": json_output,
    }

    env_overrides = {
        "OC_LLM_PROVIDER": "stub",
        "OC_LLM_FAST_POOL": "",
        "OC_LLM_QUALITY_POOL": "",
        "OC_LLM_POOL_NSFW": "",
    }
    if telemetry_self_report:
        env_overrides["OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED"] = "1"

    try:
        workspace, cleanup_base_dir = _prepare_workspace(base_path)
        if with_plugins:
            _copy_storytelling_plugin(workspace["plugins_dir"])

        db_path = workspace["data_dir"] / "openchronicle.db"
        export_path = workspace["output_dir"] / "selftest_export.json"

        with _temporary_env(env_overrides):
            container = CoreContainer(
                db_path=str(db_path),
                config_dir=str(workspace["config_dir"]),
                plugin_dir=str(workspace["plugins_dir"]),
                output_dir=str(workspace["output_dir"]),
                llm=StubLLMAdapter(),
            )

            conversation = create_conversation.execute(
                storage=container.storage,
                convo_store=container.storage,
                emit_event=container.event_logger.append,
                title="Selftest",
            )

            prompt = "Selftest prompt: ping."
            turn = asyncio.run(
                ask_conversation.execute(
                    convo_store=container.storage,
                    storage=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    emit_event=container.event_logger.append,
                    conversation_id=conversation.id,
                    prompt_text=prompt,
                    interaction_router=container.interaction_router,
                    last_n=5,
                    top_k_memory=4,
                    include_pinned_memory=False,
                    max_output_tokens=64,
                    temperature=0.0,
                    allow_pii=False,
                    privacy_gate=container.privacy_gate,
                    privacy_settings=container.privacy_settings,
                )
            )

            memory_item = remember_turn.execute(
                storage=container.storage,
                convo_store=container.storage,
                memory_store=container.storage,
                emit_event=container.event_logger.append,
                conversation_id=conversation.id,
                turn_index=turn.turn_index,
                which="assistant",
                tags=["selftest"],
                pinned=False,
                source="selftest",
            )

            updated_turn = container.storage.get_turn_by_index(conversation.id, turn.turn_index)
            if updated_turn is None:
                raise ValueError("Turn not found after remember")
            if memory_item.id not in updated_turn.memory_written_ids:
                raise ValueError("Memory link missing from turn")

            export = export_convo.execute(
                storage=container.storage,
                convo_store=container.storage,
                conversation_id=conversation.id,
                include_explain=False,
                include_verify=True,
            )
            verification = export.get("verification") if isinstance(export, dict) else None
            if isinstance(verification, dict) and verification.get("ok") is not True:
                raise ValueError("Export verification failed")

            export_path.write_text(json.dumps(export, sort_keys=True, indent=2), encoding="utf-8")

            verify_service = VerificationService(container.storage)
            verify_result = verify_service.verify_task_chain(conversation.id)
            if not verify_result.success:
                raise ValueError(verify_result.error_message or "Verification failed")

            plugin_result: dict[str, object] | None = None
            if with_plugins:
                task = run_task.submit(
                    container.orchestrator,
                    conversation.project_id,
                    "story.draft",
                    {"prompt": "Selftest story seed."},
                )
                plugin_response = asyncio.run(run_task.execute(container.orchestrator, task.id))
                draft_preview = None
                if isinstance(plugin_response, dict):
                    draft_value = plugin_response.get("draft")
                    if isinstance(draft_value, str):
                        draft_preview = draft_value[:80]
                plugin_result = {
                    "handler": "story.draft",
                    "draft_preview": draft_preview,
                    "ok": draft_preview is not None,
                }
                if plugin_result["ok"] is not True:
                    raise ValueError("Plugin handler did not return a draft")

            result.update(
                {
                    "ok": True,
                    "conversation_id": conversation.id,
                    "turn_id": turn.id,
                    "memory_ids": [memory_item.id],
                    "export_path": str(export_path),
                    "plugin_result": plugin_result,
                }
            )
    except Exception as exc:  # noqa: BLE001 - capture selftest failures
        result["failure"] = {"exception_type": exc.__class__.__name__, "message": str(exc)}
    finally:
        if result.get("ok") is True and not keep_artifacts and workspace is not None:
            if cleanup_base_dir:
                with suppress(OSError):
                    shutil.rmtree(base_path)
            else:
                for path in (
                    workspace["data_dir"],
                    workspace["config_dir"],
                    workspace["plugins_dir"],
                    workspace["output_dir"],
                ):
                    with suppress(OSError):
                        shutil.rmtree(path)
                with suppress(OSError):
                    (base_path / ".oc_selftest").unlink()

    return result
