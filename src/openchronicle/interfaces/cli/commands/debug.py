"""Debug/demo/diagnostic CLI commands: demo-summary, smoke-live, selftest, diagnose, acceptance."""

from __future__ import annotations

import argparse
import asyncio
import json

from openchronicle.core.application.use_cases import (
    ask_conversation,
    create_conversation,
    diagnose_runtime,
    run_task,
    selftest_run,
    smoke_live,
)
from openchronicle.core.domain.errors.error_codes import INTERNAL_ERROR
from openchronicle.core.domain.models.failure_category import failure_category_description
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.stdio import dispatch_request

from ._helpers import ensure_demo_agents, json_envelope, json_error_payload, print_json


def cmd_demo_summary(args: argparse.Namespace, container: CoreContainer) -> int:
    if args.use_openai:
        from openchronicle.core.infrastructure.llm.provider_facade import create_provider_aware_llm

        llm = create_provider_aware_llm()
        demo_container = CoreContainer(db_path=str(container.storage.db_path), llm=llm)
    else:
        demo_container = container

    supervisor, worker1, worker2 = ensure_demo_agents(demo_container.orchestrator, args.project_id)

    task_payload = {"text": args.text}
    if args.mix:
        task_payload["mix_strategy"] = args.mix
    elif args.mode:
        task_payload["desired_quality"] = args.mode

    task = run_task.submit(demo_container.orchestrator, args.project_id, "analysis.summary", task_payload)

    async def _run_demo() -> None:
        result = await run_task.execute(demo_container.orchestrator, task.id, agent_id=supervisor.id)
        print(json.dumps(result, indent=2))
        print(f"task_id: {task.id}")

    asyncio.run(_run_demo())
    return 0


def cmd_smoke_live(args: argparse.Namespace, container: CoreContainer) -> int:
    async def _smoke() -> int:
        result = await smoke_live.execute(
            container.orchestrator,
            prompt=args.prompt,
            provider=args.provider,
            model=args.model,
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print("\n" + "=" * 60)
            print("SMOKE TEST RESULT")
            print("=" * 60)
            print(f"Project ID:       {result.project_id}")
            print(f"Task ID:          {result.task_id}")
            print(f"Execution ID:     {result.execution_id}")
            print(f"Attempt ID:       {result.attempt_id}")
            print()
            print("PROVIDER & MODEL")
            provider_line = f"Provider Requested: {result.provider_requested or '(default)'}"
            print(provider_line)
            print(f"Provider Used:      {result.provider_used}")
            model_line = f"Model Requested:    {result.model_requested or '(default)'}"
            print(model_line)
            print(f"Model Used:         {result.model_used}")
            print()
            print("OUTCOME")
            print(f"Outcome:            {result.outcome}")
            if result.failure_category:
                category_desc = failure_category_description(result.failure_category)
                print(f"Failure Category:   {result.failure_category} ({category_desc})")
            if result.error_code:
                print(f"Error Code:         {result.error_code}")
            if result.error_message:
                print(f"Error Message:      {result.error_message}")
            print()
            print("TOKEN USAGE")
            print(f"Prompt Tokens:      {result.prompt_tokens or 'N/A'}")
            print(f"Completion Tokens:  {result.completion_tokens or 'N/A'}")
            print(f"Total Tokens:       {result.total_tokens or 'N/A'}")
            if result.latency_ms:
                print(f"Latency (ms):       {result.latency_ms}")
            print("=" * 60)

        return 0 if result.outcome == "completed" else 1

    return asyncio.run(_smoke())


def cmd_selftest(args: argparse.Namespace, container: CoreContainer) -> int:
    from openchronicle.core.infrastructure.wiring.selftest_factory import create_selftest_container

    selftest_result: dict[str, object] = selftest_run.execute(
        args.base_dir,
        json_output=args.json,
        keep_artifacts=args.keep_artifacts,
        with_plugins=not args.no_plugins,
        telemetry_self_report=args.telemetry_self_report,
        container_factory=create_selftest_container,
    )
    ok = selftest_result.get("ok") is True

    if args.json:
        selftest_failure_value = selftest_result.get("failure")
        selftest_failure_dict = selftest_failure_value if isinstance(selftest_failure_value, dict) else None
        message = (
            str(selftest_failure_dict.get("message"))
            if isinstance(selftest_failure_dict, dict) and selftest_failure_dict.get("message") is not None
            else "selftest failed"
        )
        payload = json_envelope(
            command="selftest",
            ok=ok,
            result=selftest_result if ok else None,
            error=None
            if ok
            else json_error_payload(
                error_code=None,
                message=message,
                hint=None,
                details={
                    "failure": selftest_failure_dict,
                    "workspace": selftest_result.get("workspace"),
                }
                if isinstance(selftest_failure_dict, dict)
                else {"workspace": selftest_result.get("workspace")},
            ),
        )
        print_json(payload)
        return 0 if ok else 1

    if ok:
        workspace_value = selftest_result.get("workspace")
        workspace: dict[str, object] = workspace_value if isinstance(workspace_value, dict) else {}
        print("PASS: selftest")
        print(f"conversation_id: {selftest_result.get('conversation_id')}")
        print(f"turn_id: {selftest_result.get('turn_id')}")
        print(f"memory_ids: {selftest_result.get('memory_ids')}")
        print(f"export_path: {selftest_result.get('export_path')}")
        print(f"workspace: {workspace}")
        return 0

    selftest_failure_value = selftest_result.get("failure")
    selftest_failure_dict = selftest_failure_value if isinstance(selftest_failure_value, dict) else None
    print("FAIL: selftest")
    if isinstance(selftest_failure_dict, dict):
        print(f"error: {selftest_failure_dict.get('exception_type')}: {selftest_failure_dict.get('message')}")
    return 1


def cmd_diagnose(args: argparse.Namespace, container: CoreContainer) -> int:
    report = diagnose_runtime.execute()
    if args.json:
        output_dict = {
            "timestamp_utc": report.timestamp_utc.isoformat(),
            "db_path": report.db_path,
            "db_exists": report.db_exists,
            "db_size_bytes": report.db_size_bytes,
            "db_modified_utc": report.db_modified_utc.isoformat() if report.db_modified_utc else None,
            "config_dir": report.config_dir,
            "config_dir_exists": report.config_dir_exists,
            "plugin_dir": report.plugin_dir,
            "plugin_dir_exists": report.plugin_dir_exists,
            "running_in_container_hint": report.running_in_container_hint,
            "persistence_hint": report.persistence_hint,
            "provider_env_summary": report.provider_env_summary,
        }
        print(json.dumps(output_dict, indent=2))
    else:
        print("\n" + "=" * 60)
        print("RUNTIME DIAGNOSTICS")
        print("=" * 60)
        print(f"Timestamp:           {report.timestamp_utc.isoformat()}")
        print()
        print("PATHS")
        print("  Database:")
        print(f"    Path:             {report.db_path}")
        print(f"    Exists:           {report.db_exists}")
        if report.db_exists:
            size_mb = (report.db_size_bytes or 0) / (1024 * 1024)
            print(f"    Size:             {report.db_size_bytes} bytes ({size_mb:.2f} MB)")
            if report.db_modified_utc:
                print(f"    Last modified:    {report.db_modified_utc.isoformat()}")
        print()
        print("  Config:")
        print(f"    Path:             {report.config_dir}")
        print(f"    Exists:           {report.config_dir_exists}")
        print()
        print("  Plugins:")
        print(f"    Path:             {report.plugin_dir}")
        print(f"    Exists:           {report.plugin_dir_exists}")
        print()
        print("RUNTIME")
        print(f"  In Container:       {report.running_in_container_hint}")
        print(f"  Persistence Hint:   {report.persistence_hint}")
        print()
        print("PROVIDER CONFIG")
        for key, value in sorted(report.provider_env_summary.items()):
            print(f"  {key:25} {value}")
        print("=" * 60)
    return 0


def _count_pending_tasks(container: CoreContainer, project_id: str) -> int:
    count = 0
    for task in container.storage.list_tasks_by_project(project_id):
        if task.status.value == "pending":
            count += 1
    return count


def _run_acceptance(container: CoreContainer) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    turn_ids: list[str] = []

    def _add_error(exc: Exception) -> None:
        error_code = getattr(exc, "error_code", None) or INTERNAL_ERROR
        hint = getattr(exc, "hint", None)
        errors.append({"error_code": error_code, "message": str(exc), "hint": hint})

    health_payload = dispatch_request(container, {"command": "system.health", "args": {}})
    health_result = health_payload.get("result") if isinstance(health_payload, dict) else None
    if not health_payload.get("ok"):
        health_error = health_payload.get("error") if isinstance(health_payload, dict) else None
        health_error_code = health_error.get("error_code") if isinstance(health_error, dict) else INTERNAL_ERROR
        errors.append(
            {
                "error_code": health_error_code,
                "message": "system.health failed",
                "hint": None,
            }
        )
        return {
            "status": "fail",
            "health": health_result,
            "conversation_id": None,
            "turn_ids": turn_ids,
            "export_verified": False,
            "errors": errors,
        }

    conversation = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.emit_event,
        title="Acceptance",
    )

    try:
        turn = asyncio.run(
            ask_conversation.execute(
                convo_store=container.storage,
                storage=container.storage,
                memory_store=container.storage,
                llm=container.llm,
                interaction_router=container.interaction_router,
                emit_event=container.emit_event,
                conversation_id=conversation.id,
                prompt_text="hello",
                router_policy=container.router_policy,
                last_n=5,
                top_k_memory=3,
                include_pinned_memory=True,
                allow_pii=False,
                privacy_gate=getattr(container, "privacy_gate", None),
                privacy_settings=getattr(container, "privacy_settings", None),
            )
        )
        turn_ids.append(turn.id)
    except Exception as exc:
        _add_error(exc)

    show_payload = dispatch_request(
        container,
        {
            "command": "convo.show",
            "args": {"conversation_id": conversation.id, "explain": True, "limit": 5},
        },
    )
    show_result = show_payload.get("result") if isinstance(show_payload, dict) else None
    if not show_payload.get("ok"):
        show_error = show_payload.get("error") if isinstance(show_payload, dict) else None
        show_error_code = show_error.get("error_code") if isinstance(show_error, dict) else INTERNAL_ERROR
        errors.append(
            {
                "error_code": show_error_code,
                "message": "convo.show failed",
                "hint": None,
            }
        )
    else:
        turns = show_result.get("turns", []) if isinstance(show_result, dict) else []
        if turns:
            explain = turns[-1].get("explain") if isinstance(turns[-1], dict) else None
            if not isinstance(explain, dict) or "routing_reasons" not in explain or "privacy" not in explain:
                errors.append(
                    {
                        "error_code": INTERNAL_ERROR,
                        "message": "convo.show explain missing router/privacy",
                        "hint": None,
                    }
                )

    export_payload = dispatch_request(
        container,
        {
            "command": "convo.export",
            "args": {"conversation_id": conversation.id, "verify": True, "explain": True},
        },
    )
    export_ok = bool(export_payload.get("ok"))
    if not export_ok:
        export_error = export_payload.get("error") if isinstance(export_payload, dict) else None
        export_error_code = export_error.get("error_code") if isinstance(export_error, dict) else INTERNAL_ERROR
        errors.append(
            {
                "error_code": export_error_code,
                "message": "convo.export verification failed",
                "hint": None,
            }
        )

    pending_tasks = _count_pending_tasks(container, conversation.project_id)
    if pending_tasks:
        run_many_payload = dispatch_request(
            container,
            {"command": "task.run_many", "args": {"limit": 10, "type": "convo.ask", "max_seconds": 0}},
        )
        if not run_many_payload.get("ok"):
            run_many_error = run_many_payload.get("error") if isinstance(run_many_payload, dict) else None
            run_many_error_code = (
                run_many_error.get("error_code") if isinstance(run_many_error, dict) else INTERNAL_ERROR
            )
            errors.append(
                {
                    "error_code": run_many_error_code,
                    "message": "task.run_many failed",
                    "hint": None,
                }
            )
        remaining = _count_pending_tasks(container, conversation.project_id)
        if remaining:
            errors.append(
                {
                    "error_code": INTERNAL_ERROR,
                    "message": "queued tasks remain after run_many",
                    "hint": None,
                }
            )

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "health": health_result,
        "conversation_id": conversation.id,
        "turn_ids": turn_ids,
        "export_verified": export_ok,
        "errors": errors,
    }


def cmd_acceptance(args: argparse.Namespace, container: CoreContainer) -> int:
    result = _run_acceptance(container)
    if args.json:
        print_json(result)
    else:
        status = result.get("status")
        convo_id = result.get("conversation_id")
        print(f"acceptance: {status}")
        if convo_id:
            print(f"conversation_id: {convo_id}")
    return 0 if result.get("status") == "pass" else 1
