#!/usr/bin/env python3
"""Cutover smoke test for v3 deployment.

Exercises the major HTTP surfaces against a running v3 server. Creates a
memory in an existing project, walks CRUD + search + pin + delete, then
probes the MCP transport endpoint. Used in Phase 8 step 9.

Usage:
    python scripts/smoke_test.py BASE_URL PROJECT_ID [--api-key KEY]

Example (cutover-day, against the NAS):
    python scripts/smoke_test.py http://carldog-nas:18000 \\
        87de0f7d-d6ab-4b83-8613-b2b5ff60a57b

Exits 0 on full success. On the first failure, prints the failing step
and the response body, then exits 1.

stdlib-only — no requests/httpx dependency, runs from any checkout.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    api_key: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict | list | str]:
    """Send a single HTTP request. Returns (status_code, parsed_body)."""
    headers = {"Accept": "application/json"}
    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            return exc.code, str(exc)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """HTTP handler that captures redirects instead of following them."""

    def http_error_302(self, req, fp, code, msg, headers):  # noqa: ANN001, D102
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _probe_no_redirect(url: str, api_key: str | None) -> tuple[int, str]:
    """GET a URL but do not follow redirects. Return (status, body_or_msg)."""
    headers = {"Accept": "*/*"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=5) as resp:  # noqa: S310
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc.reason or "")
    except Exception as exc:  # noqa: BLE001
        return -1, f"error: {exc!r}"


_failures = 0


def step(label: str, ok: bool, detail: str = "") -> None:
    """Print a step result. Increments the failure counter on failure."""
    global _failures
    sym = "OK " if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{sym}] {label}{suffix}")
    if not ok:
        _failures += 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("base_url", help="e.g. http://carldog-nas:18000")
    p.add_argument("project_id", help="Existing project UUID")
    p.add_argument("--api-key", default=None, help="OC_API_KEY bearer token")
    p.add_argument("--keep", action="store_true", help="Don't delete the test memory")
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    api = args.api_key
    print(f"Smoke test: {base}  project_id={args.project_id}")

    # 1. Liveness (top-level, used by Docker healthcheck)
    s, body = request(f"{base}/health", api_key=api)
    step("/health (liveness)", s == 200, f"status={s} body={body!r}"[:120])

    # 2. Detailed health (under /api/v1)
    s, body = request(f"{base}/api/v1/health", api_key=api)
    healthy = s == 200 and isinstance(body, dict) and body.get("db_path")
    step("/api/v1/health", healthy, f"status={s}, db_path={body.get('db_path') if isinstance(body, dict) else '?'}")

    # 3. Maintenance loop running
    s, body = request(f"{base}/api/v1/maintenance/status", api_key=api)
    enabled = s == 200 and isinstance(body, dict) and body.get("enabled") is True
    step("/api/v1/maintenance/status", enabled, f"enabled={body.get('enabled') if isinstance(body, dict) else '?'}")

    # 4. Project list contains our target project
    s, body = request(f"{base}/api/v1/project", api_key=api)
    found_project = isinstance(body, list) and any(p.get("id") == args.project_id for p in body if isinstance(p, dict))
    step(
        "/api/v1/project (list)",
        s == 200 and found_project,
        f"status={s}, project_id present={found_project}",
    )

    # 5. Save a smoke-test memory
    marker = f"smoke-test-{int(time.time())}"
    save_body = {
        "content": f"smoke test memory {marker}",
        "tags": ["smoke-test"],
        "project_id": args.project_id,
        "pinned": False,
    }
    s, body = request(f"{base}/api/v1/memory", "POST", save_body, api_key=api)
    memory_id = body.get("id") if isinstance(body, dict) else None
    step(
        f"POST /api/v1/memory ({marker})",
        s in (200, 201) and bool(memory_id),
        f"status={s}, id={memory_id}",
    )
    if not memory_id:
        return _exit_summary()

    # 6. Read it back
    s, body = request(f"{base}/api/v1/memory/{memory_id}", api_key=api)
    step(f"GET /api/v1/memory/{memory_id}", s == 200)

    # 7. Search finds it (validates FTS5 indexing on insert)
    s, body = request(
        f"{base}/api/v1/memory/search?query={marker}&project_id={args.project_id}",
        api_key=api,
    )
    found = isinstance(body, list) and any(marker in (m.get("content", "")) for m in body)
    step(f"GET /api/v1/memory/search?query={marker}", found, f"results={len(body) if isinstance(body, list) else '?'}")

    # 8. Pin
    s, body = request(f"{base}/api/v1/memory/{memory_id}/pin", "PUT", {"pinned": True}, api_key=api)
    step("PUT /memory/{id}/pin", s == 200)

    # 9. Cleanup (skip with --keep for inspection)
    if not args.keep:
        s, body = request(f"{base}/api/v1/memory/{memory_id}", "DELETE", api_key=api)
        step(f"DELETE /api/v1/memory/{memory_id}", s == 200)
    else:
        print(f"  [SKIP] DELETE — left memory {memory_id} in place (--keep)")

    # 10. MCP transport reachable
    # FastMCP's streamable_http_app is mounted at /mcp (no trailing slash).
    # GET typically responds 307 (redirect to its inner transport handler)
    # or 405. We just want to confirm the mount exists, not run a full
    # MCP handshake. Pass through redirects raw — urllib follows them by
    # default; we trap that and treat the redirect itself as success.
    s, _ = _probe_no_redirect(f"{base}/mcp", api)
    step("/mcp reachable", s in (200, 307, 308, 400, 405, 406), f"status={s}")

    return _exit_summary()


def _exit_summary() -> int:
    if _failures:
        print(f"\nFAILED ({_failures} step{'s' if _failures > 1 else ''} failed).")
        return 1
    print("\nPASSED — all smoke checks green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
