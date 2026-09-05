"""Run a bounded, disposable REST/MCP performance probe.

The probe starts a real unified OC server on loopback, seeds deterministic
synthetic data, and runs a closed-loop workload against its real REST or
streamable-HTTP MCP interface. It never accepts a remote target and always
owns the temporary database and child process it creates.

Examples::

    python scripts/probe_performance.py --transport rest --mode keyword
    python scripts/probe_performance.py --transport mcp --mode hybrid \
        --clients 1,4,8,16 --out probe.json
    python scripts/probe_performance.py --check-rate-limit

The default 5-second warm-up and 60-second measurement are intentionally
longer than the unit tests. Use ``--warmup-seconds 0 --duration-seconds 1``
for a local smoke run. Reports contain aggregates only; request payloads,
memory IDs, paths, and exception text are never emitted.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.client
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Literal, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from openchronicle.version import package_version  # noqa: E402

DEFAULT_CLIENTS = (1, 4, 8, 16)
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RUNTIME_SECONDS = 600.0
DEFAULT_SEED = 20260904
PROJECT_ID = "probe-project"
CONTENT_SIZE = 192
VECTOR_DIMENSIONS = 32
SAME_RUN_AFFINITY_CPUS_PER_CONDITION = 8

Lane = Literal["fixed", "growth"]
Mode = Literal["keyword", "semantic", "hybrid"]
ProviderProfile = Literal["none", "stub", "simulated-400ms"]
TransportName = Literal["rest", "mcp"]


class ProbeError(RuntimeError):
    """A user-actionable probe setup or orchestration error."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ProbeConfig:
    transport: TransportName = "rest"
    lane: Lane = "fixed"
    mode: Mode = "keyword"
    provider_profile: ProviderProfile = "none"
    corpus_size: int = 1000
    clients: tuple[int, ...] = DEFAULT_CLIENTS
    warmup_seconds: float = 5.0
    duration_seconds: float = 60.0
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    max_runtime_seconds: float = DEFAULT_MAX_RUNTIME_SECONDS
    seed: int = DEFAULT_SEED
    instrumentation_state: str = "uninstrumented"
    source_root: Path = REPOSITORY_ROOT
    scrape_interval_seconds: float | None = None
    start_barrier_dir: Path | None = None
    start_barrier_label: str | None = None
    cpu_affinity_mask: int | None = None


@dataclass(frozen=True)
class OperationResult:
    operation: str
    started_at: float
    duration_seconds: float
    completed: bool
    timed_out: bool
    failure_category: str | None = None
    status_code: int | None = None


@dataclass(frozen=True)
class CorpusSnapshot:
    """Sanitized corpus state captured outside the measured window."""

    memory_count: int
    vector_count: int
    fingerprint: str


@dataclass
class OperationSummary:
    attempted: int = 0
    completed: int = 0
    failed: int = 0
    timed_out: int = 0
    durations: list[float] = field(default_factory=list)
    censored_durations: list[float] = field(default_factory=list)
    status_classes: Counter[str] = field(default_factory=Counter)
    failure_categories: Counter[str] = field(default_factory=Counter)

    def add(self, result: OperationResult) -> None:
        self.attempted += 1
        if result.completed:
            self.completed += 1
            self.durations.append(result.duration_seconds)
        else:
            self.failed += 1
        if result.timed_out:
            self.timed_out += 1
            self.censored_durations.append(result.duration_seconds)
        if result.status_code is not None:
            self.status_classes[f"{result.status_code // 100}xx"] += 1
        if result.failure_category is not None:
            self.failure_categories[result.failure_category] += 1

    def as_dict(self) -> dict[str, Any]:
        completed_durations = sorted(self.durations)
        return {
            "attempted": self.attempted,
            "completed": self.completed,
            "failed": self.failed,
            "timed_out": self.timed_out,
            "completion_rate": round(self.completed / self.attempted, 4) if self.attempted else None,
            "throughput_completed_per_second": None,
            "sample_count": self.completed,
            "p50_seconds": _quantile(completed_durations, 0.50),
            "p95_seconds": _quantile(completed_durations, 0.95) if self.completed >= 100 else None,
            "p99_seconds": _quantile(completed_durations, 0.99) if self.completed >= 1000 else None,
            "p95_sample_sufficient": self.completed >= 100,
            "p99_sample_sufficient": self.completed >= 1000,
            "timeout_duration_sample_count": len(self.censored_durations),
            "timeout_duration_p50_seconds": _quantile(sorted(self.censored_durations), 0.50),
            "timeout_duration_max_seconds": round(max(self.censored_durations), 6) if self.censored_durations else None,
            "status_classes": dict(sorted(self.status_classes.items())),
            "failure_categories": dict(sorted(self.failure_categories.items())),
        }


def _quantile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, int((len(values) - 1) * fraction)))
    return round(values[index], 6)


@dataclass
class ScrapeSummary:
    """Sanitized results from the optional direct exporter scrape loop."""

    attempted: int = 0
    completed: int = 0
    failed: int = 0
    durations: list[float] = field(default_factory=list)
    all_durations: list[float] = field(default_factory=list)

    def record(self, duration_seconds: float, completed: bool) -> None:
        self.attempted += 1
        self.all_durations.append(duration_seconds)
        if completed:
            self.completed += 1
            self.durations.append(duration_seconds)
        else:
            self.failed += 1

    def as_dict(self) -> dict[str, Any]:
        durations = sorted(self.durations)
        return {
            "attempted": self.attempted,
            "completed": self.completed,
            "failed": self.failed,
            "completion_rate": round(self.completed / self.attempted, 4) if self.attempted else None,
            "sample_count": self.completed,
            "all_durations_seconds": [round(duration, 6) for duration in self.all_durations],
            "p50_seconds": _quantile(durations, 0.50),
            "p95_seconds": _quantile(durations, 0.95) if self.completed >= 100 else None,
            "max_seconds": round(max(durations), 6) if durations else None,
            "max_attempt_seconds": round(max(self.all_durations), 6) if self.all_durations else None,
        }


class MetricsScraper:
    """Bounded local scrape-path load generator for controlled measurements."""

    def __init__(self, base_url: str, interval_seconds: float, timeout_seconds: float) -> None:
        self._url = f"{base_url.rstrip('/')}/metrics"
        self._interval_seconds = interval_seconds
        self._timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._summary = ScrapeSummary()
        self._thread = threading.Thread(target=self._run, name="oc-probe-scraper", daemon=False)

    def start(self) -> None:
        self._thread.start()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._summary.as_dict()

    def reset(self) -> None:
        with self._lock:
            self._summary = ScrapeSummary()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=max(5.0, self._timeout_seconds + 1.0))
        if self._thread.is_alive():
            raise ProbeError("scrape_shutdown", "scrape worker did not stop within the cleanup bound")

    def _run(self) -> None:
        next_run = time.monotonic()
        while not self._stop_event.wait(max(0.0, next_run - time.monotonic())):
            started = time.perf_counter()
            completed = False
            try:
                with self._opener.open(self._url, timeout=self._timeout_seconds) as response:
                    response.read()
                    completed = 200 <= response.status < 300
            except OSError, TimeoutError, urllib.error.URLError:
                completed = False
            duration = time.perf_counter() - started
            with self._lock:
                self._summary.record(duration, completed)
            next_run += self._interval_seconds
            now = time.monotonic()
            if next_run <= now:
                next_run = now + self._interval_seconds


def _process_rss_bytes(pid: int) -> int | None:
    """Read a child process working-set size without adding a dependency."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x0410, False, pid)
        if not handle:
            return None
        try:
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(ProcessMemoryCounters)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return None
            return int(counters.WorkingSetSize)
        finally:
            kernel32.CloseHandle(handle)

    status_path = Path(f"/proc/{pid}/status")
    try:
        for line in status_path.read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError, ValueError, IndexError:
        return None
    return None


class ProcessMemorySampler:
    """Sample the disposable server's RSS for the fixed-workload gate."""

    def __init__(self, pid: int, interval_seconds: float = 0.1) -> None:
        self._pid = pid
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._peak_rss_bytes: int | None = None
        self._sample_count = 0
        self._supported: bool | None = None
        self._thread = threading.Thread(target=self._run, name="oc-probe-memory", daemon=False)

    def start(self) -> None:
        self._thread.start()

    def reset_peak(self) -> None:
        with self._lock:
            self._peak_rss_bytes = None
            self._sample_count = 0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "supported": self._supported is True,
                "peak_rss_bytes": self._peak_rss_bytes,
                "sample_count": self._sample_count,
            }

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise ProbeError("memory_shutdown", "memory sampler did not stop within the cleanup bound")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            rss = _process_rss_bytes(self._pid)
            with self._lock:
                self._sample_count += 1
                if rss is not None:
                    self._supported = True
                    if self._peak_rss_bytes is None or rss > self._peak_rss_bytes:
                        self._peak_rss_bytes = rss
                elif self._supported is None:
                    self._supported = False
            if self._stop_event.wait(self._interval_seconds):
                break


class EventLoopLagTracker:
    """Measure maximum scheduling lateness of a bounded 10 ms async tick."""

    def __init__(self, interval_seconds: float = 0.01) -> None:
        self._interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._lateness_seconds: list[float] = []
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    def snapshot(self) -> dict[str, Any]:
        lateness = sorted(self._lateness_seconds)
        return {
            "interval_seconds": self._interval_seconds,
            "sample_count": len(lateness),
            "p95_lateness_seconds": _quantile(lateness, 0.95),
            "max_lateness_seconds": round(max(lateness), 6) if lateness else None,
        }

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        next_due = loop.time() + self._interval_seconds
        while not self._stop_event.is_set():
            await asyncio.sleep(max(0.0, next_due - loop.time()))
            if self._stop_event.is_set():
                break
            now = loop.time()
            self._lateness_seconds.append(max(0.0, now - next_due))
            next_due += self._interval_seconds
            if next_due <= now:
                next_due = now + self._interval_seconds


def parse_clients(value: str) -> tuple[int, ...]:
    """Parse and validate a comma-separated client-count list."""
    try:
        clients = tuple(sorted({int(part.strip()) for part in value.split(",") if part.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("clients must be comma-separated positive integers") from exc
    if not clients or any(client < 1 or client > 256 for client in clients):
        raise argparse.ArgumentTypeError("clients must contain values from 1 through 256")
    return clients


def parse_affinity_mask(value: str) -> int:
    """Parse a positive Windows/Linux process-affinity bit mask."""
    try:
        mask = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "cpu-affinity-mask must be an integer or 0x-prefixed hexadecimal value"
        ) from exc
    if mask <= 0 or mask >= 1 << 64:
        raise argparse.ArgumentTypeError("cpu-affinity-mask must fit in a positive 64-bit mask")
    return mask


def _apply_process_affinity(mask: int | None) -> None:
    """Constrain this driver and its child server to the requested CPUs."""
    if mask is None:
        return
    cpus = tuple(index for index in range(mask.bit_length()) if mask & (1 << index))
    if platform.system() == "Windows":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        set_process_affinity_mask = kernel32.SetProcessAffinityMask
        set_process_affinity_mask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        set_process_affinity_mask.restype = ctypes.c_int
        if not set_process_affinity_mask(kernel32.GetCurrentProcess(), mask):
            error = ctypes.get_last_error()
            raise ProbeError("affinity", f"could not set process affinity mask 0x{mask:x} (winerror {error})")
        return
    if hasattr(os, "sched_setaffinity"):
        try:
            os.sched_setaffinity(0, cpus)
        except OSError as exc:
            raise ProbeError("affinity", f"could not set process affinity mask 0x{mask:x}") from exc
        return
    raise ProbeError("affinity", "process affinity is not supported on this platform")


def _failure_category(status_code: int | None, exc: BaseException | None = None) -> str:
    if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.HTTPError):
        status_code = exc.code
    if status_code is not None:
        if 400 <= status_code < 500:
            return "http_4xx"
        if status_code >= 500:
            return "http_5xx"
        return "invalid_response"
    if isinstance(exc, urllib.error.URLError):
        return "connection"
    return "transport_error"


def _is_timeout(exc: BaseException | None) -> bool:
    return isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)


class RestTransport:
    """Small standard-library REST client with optional per-worker keep-alive."""

    def __init__(self, base_url: str, timeout_seconds: float, *, keep_alive: bool = False) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._keep_alive = keep_alive
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._url_parts = urllib.parse.urlsplit(self._base_url)
        self._connection: http.client.HTTPConnection | None = None

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | bool] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[OperationResult, Any]:
        query = urllib.parse.urlencode(params or {})
        url = f"{self._base_url}{path}" + (f"?{query}" if query else "")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        started = time.perf_counter()
        status_code: int | None = None
        response_body: bytes = b""
        error: BaseException | None = None
        try:
            if self._keep_alive:
                target = f"{self._url_parts.path.rstrip('/')}{path}" + (f"?{query}" if query else "")
                if self._connection is None:
                    if self._url_parts.scheme != "http" or self._url_parts.hostname is None:
                        raise ValueError("keep-alive REST transport requires an HTTP origin")
                    self._connection = http.client.HTTPConnection(
                        self._url_parts.hostname,
                        self._url_parts.port,
                        timeout=self._timeout,
                    )
                else:
                    self._connection.timeout = self._timeout
                try:
                    self._connection.request(
                        method,
                        target,
                        body=body,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "Connection": "keep-alive",
                        },
                    )
                    response = self._connection.getresponse()
                    status_code = response.status
                    response_body = response.read()
                    if response.will_close:
                        self.close()
                except (OSError, http.client.HTTPException) as exc:
                    self.close()
                    raise urllib.error.URLError(exc) from exc
            else:
                with self._opener.open(request, timeout=self._timeout) as response:
                    status_code = response.status
                    response_body = response.read()
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            error = exc
            try:
                response_body = exc.read()
            except OSError:
                response_body = b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = exc
        duration = time.perf_counter() - started
        if error is not None or status_code is None or not 200 <= status_code < 300:
            return (
                OperationResult(
                    operation="transport",
                    started_at=started,
                    duration_seconds=duration,
                    completed=False,
                    timed_out=_is_timeout(error),
                    failure_category=_failure_category(status_code, error),
                    status_code=status_code,
                ),
                None,
            )
        try:
            decoded: Any = json.loads(response_body.decode("utf-8")) if response_body else None
        except UnicodeDecodeError, json.JSONDecodeError:
            return (
                OperationResult(
                    operation="transport",
                    started_at=started,
                    duration_seconds=duration,
                    completed=False,
                    timed_out=False,
                    failure_category="invalid_response",
                    status_code=status_code,
                ),
                None,
            )
        return (
            OperationResult(
                operation="transport",
                started_at=started,
                duration_seconds=duration,
                completed=True,
                timed_out=False,
                status_code=status_code,
            ),
            decoded,
        )


class SimulatedEmbeddingServer:
    """Local OpenAI-compatible endpoint with switchable serialized delay."""

    def __init__(self, dimensions: int = VECTOR_DIMENSIONS) -> None:
        self._dimensions = dimensions
        self._delay_seconds = 0.0
        self._delay_lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path.rstrip("/") != "/v1/embeddings":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    request_data = json.loads(self.rfile.read(length).decode("utf-8"))
                    inputs = request_data.get("input", [])
                    if isinstance(inputs, str):
                        inputs = [inputs]
                    if not isinstance(inputs, list) or not all(isinstance(item, str) for item in inputs):
                        self.send_error(400)
                        return
                except ValueError, UnicodeDecodeError, json.JSONDecodeError:
                    self.send_error(400)
                    return
                # HTTPServer, deliberately not ThreadingHTTPServer, serializes
                # requests so the profile models one serialized upstream.
                with owner._delay_lock:
                    delay = owner._delay_seconds
                if delay:
                    time.sleep(delay)
                response = {
                    "object": "list",
                    "data": [
                        {"object": "embedding", "embedding": owner._vector(text), "index": index}
                        for index, text in enumerate(inputs)
                    ],
                    "model": "probe-simulated",
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                }
                encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="probe-embedding", daemon=True)
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{self._server.server_port}/v1"

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < self._dimensions:
            block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
            for offset in range(0, len(block), 4):
                if len(values) >= self._dimensions:
                    break
                raw = int.from_bytes(block[offset : offset + 4], "big")
                values.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
            counter += 1
        return values

    def set_delay(self, seconds: float) -> None:
        with self._delay_lock:
            self._delay_seconds = seconds

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)


class McpSession:
    """One streamable-HTTP MCP client session, used by one probe client."""

    def __init__(self, url: str, timeout_seconds: float) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._stack: Any = None
        self._session: Any = None

    async def __aenter__(self) -> McpSession:
        try:
            from mcp.client.session import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise ProbeError("missing_mcp_dependency", "MCP transport requires the repository's mcp extra") from exc
        from contextlib import AsyncExitStack

        self._stack = AsyncExitStack()
        read_stream, write_stream, _ = await self._stack.enter_async_context(
            streamablehttp_client(
                self._url,
                timeout=self._timeout_seconds,
                sse_read_timeout=self._timeout_seconds,
                terminate_on_close=True,
            )
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=self._timeout_seconds),
            )
        )
        await asyncio.wait_for(self._session.initialize(), timeout=self._timeout_seconds)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._stack is not None:
            await self._stack.__aexit__(exc_type, exc, tb)

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, Any, str | None]:
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return False, None, "timeout"
        except Exception:
            return False, None, "mcp_error"
        if getattr(result, "isError", False):
            return False, None, "mcp_error"
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return True, _unwrap_mcp_payload(structured), None
        content = getattr(result, "content", [])
        for block in content:
            text_value = getattr(block, "text", None)
            if text_value:
                try:
                    return True, _unwrap_mcp_payload(json.loads(text_value)), None
                except json.JSONDecodeError:
                    return True, text_value, None
        return True, None, None


class WorkloadClient:
    """Transport-neutral setup and operation execution."""

    def __init__(self, config: ProbeConfig, base_url: str) -> None:
        self.config = config
        self.base_url = base_url
        self.project_id = PROJECT_ID
        self.memory_ids: tuple[str, ...] = ()

    async def setup(self, deadline: float) -> None:
        if time.perf_counter() >= deadline:
            raise ProbeError("runtime_cap", "probe reached its maximum runtime before corpus setup")
        if self.config.transport == "rest":
            rest = RestTransport(self.base_url, self.config.request_timeout_seconds)
            result, body = await asyncio.to_thread(
                rest.request,
                "POST",
                "/api/v1/project",
                payload={"name": "probe-project"},
            )
            _require_success(result, "project setup")
            if not isinstance(body, dict) or not isinstance(body.get("id"), str):
                raise ProbeError("invalid_response", "project setup returned no project id")
            self.project_id = body["id"]
            await self._seed_rest(rest, deadline)
            return
        async with McpSession(f"{self.base_url}/mcp/", self.config.request_timeout_seconds) as session:
            ok, body, failure = await session.call("project_create", {"name": "probe-project"})
            if not ok:
                raise ProbeError(failure or "mcp_error", "project setup failed")
            if not isinstance(body, dict) or not isinstance(body.get("id"), str):
                raise ProbeError("invalid_response", "project setup returned no project id")
            self.project_id = body["id"]
            await self._seed_mcp(session, deadline)

    async def _seed_rest(self, rest: RestTransport, deadline: float) -> None:
        ids: list[str] = []
        for index in range(self.config.corpus_size):
            if time.perf_counter() >= deadline:
                raise ProbeError("runtime_cap", "probe reached its maximum runtime during corpus setup")
            result, body = await asyncio.to_thread(
                rest.request,
                "POST",
                "/api/v1/memory",
                payload=_memory_payload(index, self.project_id, self.config.seed),
            )
            _require_success(result, "corpus setup")
            if not isinstance(body, dict) or not isinstance(body.get("id"), str):
                raise ProbeError("invalid_response", "corpus setup returned no memory id")
            ids.append(body["id"])
        self.memory_ids = tuple(ids)

    async def _seed_mcp(self, session: McpSession, deadline: float) -> None:
        ids: list[str] = []
        for index in range(self.config.corpus_size):
            if time.perf_counter() >= deadline:
                raise ProbeError("runtime_cap", "probe reached its maximum runtime during corpus setup")
            ok, body, failure = await session.call(
                "memory_save",
                _memory_payload(index, self.project_id, self.config.seed),
            )
            if not ok:
                raise ProbeError(failure or "mcp_error", "corpus setup failed")
            if not isinstance(body, dict) or not isinstance(body.get("id"), str):
                raise ProbeError("invalid_response", "corpus setup returned no memory id")
            ids.append(body["id"])
        self.memory_ids = tuple(ids)

    async def snapshot(self) -> CorpusSnapshot:
        if self.config.transport == "rest":
            rest = RestTransport(self.base_url, self.config.request_timeout_seconds)
            list_result, list_body = await asyncio.to_thread(
                rest.request,
                "GET",
                "/api/v1/memory",
                params={"limit": 10000, "project_id": self.project_id, "compact": "false", "order_by": "created_at"},
            )
            stats_result, stats_body = await asyncio.to_thread(
                rest.request,
                "GET",
                "/api/v1/memory/stats",
                params={"project_id": self.project_id, "top_tags": 1},
            )
            health_result, health_body = await asyncio.to_thread(rest.request, "GET", "/api/v1/health")
        else:
            async with McpSession(f"{self.base_url}/mcp/", self.config.request_timeout_seconds) as session:
                ok, list_body, failure = await session.call(
                    "memory_list",
                    {"limit": 10000, "project_id": self.project_id, "compact": False, "order_by": "created_at"},
                )
                list_result = OperationResult("snapshot", time.perf_counter(), 0.0, ok, failure == "timeout", failure)
                ok, stats_body, failure = await session.call(
                    "memory_stats",
                    {"project_id": self.project_id, "top_tags": 1},
                )
                stats_result = OperationResult("snapshot", time.perf_counter(), 0.0, ok, failure == "timeout", failure)
                ok, health_body, failure = await session.call("health", {})
                health_result = OperationResult("snapshot", time.perf_counter(), 0.0, ok, failure == "timeout", failure)
        _require_success(list_result, "corpus listing")
        _require_success(stats_result, "corpus count")
        _require_success(health_result, "corpus health snapshot")
        if not isinstance(list_body, list):
            raise ProbeError("invalid_response", "corpus snapshot was not a list")
        if not isinstance(stats_body, dict) or not isinstance(stats_body.get("total"), int):
            raise ProbeError("invalid_response", "corpus count did not contain a total")
        if stats_body["total"] < 0:
            raise ProbeError("invalid_response", "corpus count was negative")
        canonical_rows: list[dict[str, Any]] = []
        for row in list_body:
            if not isinstance(row, dict):
                raise ProbeError("invalid_response", "corpus snapshot contained a non-object row")
            canonical_rows.append(
                {
                    "content": row.get("content"),
                    "tags": row.get("tags"),
                    "pinned": row.get("pinned"),
                    "source": row.get("source"),
                }
            )
        canonical = json.dumps(canonical_rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return CorpusSnapshot(
            memory_count=stats_body["total"],
            vector_count=_vector_count_from_health(health_body),
            fingerprint=hashlib.sha256(canonical).hexdigest(),
        )

    async def operation(
        self,
        operation: str,
        worker_id: int,
        sequence_number: int,
        *,
        rest: RestTransport | None = None,
        session: McpSession | None = None,
    ) -> OperationResult:
        started = time.perf_counter()
        try:
            if self.config.transport == "rest":
                if rest is None:
                    rest = RestTransport(self.base_url, self.config.request_timeout_seconds)
                method, path, kwargs = self._rest_operation(operation, worker_id, sequence_number)
                result, body = await asyncio.to_thread(
                    rest.request,
                    method,
                    path,
                    **kwargs,
                )
                return _with_operation(result, operation, body)
            if session is None:
                raise ProbeError("mcp_error", "MCP operation was attempted without a client session")
            name, arguments = self._mcp_operation(operation, worker_id, sequence_number)
            ok, body, failure = await session.call(name, arguments)
            if ok and not _valid_operation_body(operation, body):
                ok = False
                failure = "invalid_response"
            return OperationResult(
                operation=operation,
                started_at=started,
                duration_seconds=time.perf_counter() - started,
                completed=ok,
                timed_out=failure == "timeout",
                failure_category=failure,
            )
        except ProbeError:
            raise
        except TimeoutError:
            return OperationResult(operation, started, time.perf_counter() - started, False, True, "timeout")
        except Exception as exc:
            return OperationResult(
                operation,
                started,
                time.perf_counter() - started,
                False,
                _is_timeout(exc),
                _failure_category(None, exc),
            )

    def _rest_operation(self, operation: str, worker_id: int, sequence_number: int) -> tuple[str, str, dict[str, Any]]:
        if operation == "search":
            return (
                "GET",
                "/api/v1/memory/search",
                {
                    "params": {
                        "query": _query(sequence_number),
                        "mode": self.config.mode,
                        "top_k": 8,
                        "project_id": self.project_id,
                        "compact": "true",
                        "pinned_limit": 0,
                    }
                },
            )
        if operation == "list":
            return (
                "GET",
                "/api/v1/memory",
                {
                    "params": {
                        "limit": 20,
                        "project_id": self.project_id,
                        "compact": "true",
                        "order_by": "created_at",
                    }
                },
            )
        return (
            "POST",
            "/api/v1/memory",
            {"payload": _memory_payload(worker_id * 1_000_000 + sequence_number, self.project_id, self.config.seed)},
        )

    def _mcp_operation(self, operation: str, worker_id: int, sequence_number: int) -> tuple[str, dict[str, Any]]:
        if operation == "search":
            return (
                "memory_search",
                {
                    "query": _query(sequence_number),
                    "mode": self.config.mode,
                    "top_k": 8,
                    "project_id": self.project_id,
                    "compact": True,
                    "pinned_limit": 0,
                },
            )
        if operation == "list":
            return (
                "memory_list",
                {"limit": 20, "project_id": self.project_id, "compact": True, "order_by": "created_at"},
            )
        return (
            "memory_save",
            _memory_payload(worker_id * 1_000_000 + sequence_number, self.project_id, self.config.seed),
        )


def _require_success(result: OperationResult, context: str) -> None:
    if not result.completed:
        raise ProbeError(result.failure_category or "transport_error", f"{context} failed")


def _with_operation(result: OperationResult, operation: str, body: Any = None) -> OperationResult:
    completed = result.completed
    failure_category = result.failure_category
    if completed and not _valid_operation_body(operation, body):
        completed = False
        failure_category = "invalid_response"
    return OperationResult(
        operation=operation,
        started_at=result.started_at,
        duration_seconds=result.duration_seconds,
        completed=completed,
        timed_out=result.timed_out,
        failure_category=failure_category,
        status_code=result.status_code,
    )


def _unwrap_mcp_payload(body: Any) -> Any:
    """Normalize SDK structured-content wrappers without exposing them."""
    if isinstance(body, dict) and set(body) == {"result"}:
        return body["result"]
    return body


def _valid_operation_body(operation: str, body: Any) -> bool:
    if operation in {"search", "list"}:
        return isinstance(body, list)
    return isinstance(body, dict) and isinstance(body.get("id"), str)


def _memory_payload(index: int, project_id: str, seed: int) -> dict[str, Any]:
    topic = index % 20
    content = f"performance probe seed {seed} topic {topic:02d} item {index:08d} " + ("x" * CONTENT_SIZE)
    return {
        "content": content,
        "project_id": project_id,
        "tags": ["probe", f"topic-{topic:02d}"],
        "pinned": False,
    }


def _vector_count_from_health(body: Any) -> int:
    if not isinstance(body, dict):
        raise ProbeError("invalid_response", "health snapshot was not an object")
    embedding_status = body.get("embedding_status")
    if not isinstance(embedding_status, dict):
        raise ProbeError("invalid_response", "health snapshot contained no embedding status")
    if embedding_status.get("provider") == "none" or embedding_status.get("status") == "disabled":
        return 0
    embedded = embedding_status.get("embedded")
    if not isinstance(embedded, int) or embedded < 0:
        raise ProbeError("invalid_response", "health snapshot contained no valid embedding count")
    return embedded


def _query(sequence_number: int) -> str:
    return f"performance probe topic {sequence_number % 20:02d}"


def operation_for(lane: Lane, random_value: float) -> str:
    """Map a deterministic random draw to the plan's workload mix."""
    if lane == "fixed":
        return "search" if random_value < 0.90 else "list"
    if random_value < 0.70:
        return "search"
    if random_value < 0.90:
        return "save"
    return "list"


async def _run_clients(
    client: WorkloadClient,
    config: ProbeConfig,
    client_count: int,
    *,
    duration_seconds: float,
    collect: bool,
    max_runtime_deadline: float,
) -> tuple[list[OperationResult], float, list[OperationResult]]:
    """Run closed-loop clients for a bounded duration."""
    result_lock = asyncio.Lock()
    ready_event = asyncio.Event()
    start_event = asyncio.Event()
    burst_results: list[OperationResult] = []
    phase_results: list[OperationResult] = []
    ready_count = 0
    ready_lock = asyncio.Lock()
    measurement_start = 0.0

    async def record(sample: OperationResult) -> None:
        async with result_lock:
            phase_results.append(sample)

    async def await_start() -> None:
        nonlocal ready_count
        async with ready_lock:
            ready_count += 1
            if ready_count == client_count:
                ready_event.set()
        await start_event.wait()

    async def worker(worker_id: int) -> None:
        rng = random.Random(config.seed + worker_id)
        rest = (
            RestTransport(client.base_url, config.request_timeout_seconds, keep_alive=True)
            if config.transport == "rest"
            else None
        )
        if config.transport == "mcp":
            async with McpSession(f"{client.base_url}/mcp/", config.request_timeout_seconds) as session:
                await await_start()
                await _worker_measurement(
                    client,
                    config,
                    worker_id,
                    rng,
                    measurement_start + duration_seconds,
                    max_runtime_deadline,
                    collect,
                    rest,
                    session,
                    record,
                    burst_results,
                )
            return
        try:
            await await_start()
            await _worker_measurement(
                client,
                config,
                worker_id,
                rng,
                measurement_start + duration_seconds,
                max_runtime_deadline,
                collect,
                rest,
                None,
                record,
                burst_results,
            )
        finally:
            if rest is not None:
                rest.close()

    if time.perf_counter() >= max_runtime_deadline:
        raise ProbeError("runtime_cap", "probe reached its maximum runtime before clients started")
    tasks = [asyncio.create_task(worker(worker_id)) for worker_id in range(client_count)]
    try:
        remaining_runtime = max_runtime_deadline - time.perf_counter()
        await asyncio.wait_for(ready_event.wait(), timeout=min(30.0, remaining_runtime))
        measurement_start = time.perf_counter()
        start_event.set()
    except TimeoutError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise ProbeError("client_start_timeout", "clients did not reach the bounded start barrier") from None
    try:
        remaining_runtime = max_runtime_deadline - time.perf_counter()
        if remaining_runtime <= 0:
            raise ProbeError("runtime_cap", "probe reached its maximum runtime before measurement")
        await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=min(duration_seconds + config.request_timeout_seconds + 2, remaining_runtime),
        )
    except TimeoutError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if time.perf_counter() >= max_runtime_deadline:
            raise ProbeError("runtime_cap", "probe reached its maximum runtime while draining clients") from None
        raise ProbeError("drain_timeout", "client drain exceeded its bounded timeout") from None
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    elapsed = time.perf_counter() - measurement_start
    return phase_results, elapsed, burst_results


async def _worker_measurement(
    client: WorkloadClient,
    config: ProbeConfig,
    worker_id: int,
    rng: random.Random,
    measurement_end: float,
    max_runtime_deadline: float,
    burst_enabled: bool,
    rest: RestTransport | None,
    session: McpSession | None,
    record: Callable[[OperationResult], Awaitable[None]],
    burst_results: list[OperationResult],
) -> None:
    """Run one simultaneous burst, then the closed-loop client."""
    if measurement_end <= time.perf_counter():
        return
    sequence_number = 0
    if burst_enabled:
        burst = await client.operation("search", worker_id, sequence_number, rest=rest, session=session)
        burst_results.append(burst)
        await record(burst)
        sequence_number += 1
    while True:
        now = time.perf_counter()
        if now >= max_runtime_deadline or now >= measurement_end:
            return
        operation = operation_for(config.lane, rng.random())
        sample = await client.operation(operation, worker_id, sequence_number, rest=rest, session=session)
        sequence_number += 1
        await record(sample)


async def _wait_for_start_barrier(directory: Path, label: str, *, deadline: float) -> None:
    """Signal post-warm-up readiness and wait for the matrix coordinator."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{label}.ready").write_text("ready\n", encoding="utf-8")
    except OSError as exc:
        raise ProbeError("barrier_setup", "could not create the matrix readiness marker") from exc
    start_path = directory / "start"
    abort_path = directory / "abort"
    while not start_path.exists():
        if abort_path.exists():
            raise ProbeError("barrier_aborted", "matrix coordinator aborted the shared start")
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise ProbeError("barrier_timeout", "matrix start barrier was not released before the runtime cap")
        await asyncio.sleep(min(0.05, remaining))


async def run_client_count(
    client: WorkloadClient,
    config: ProbeConfig,
    client_count: int,
    deadline: float,
    *,
    start_barrier: tuple[Path, str] | None = None,
) -> dict[str, Any]:
    if time.perf_counter() >= deadline:
        raise ProbeError("runtime_cap", "probe reached its maximum runtime before the case started")
    starting_snapshot = await client.snapshot()
    warmup_results, _, _ = await _run_clients(
        client,
        config,
        client_count,
        duration_seconds=config.warmup_seconds,
        collect=False,
        max_runtime_deadline=deadline,
    )
    post_warmup_snapshot = await client.snapshot()
    if start_barrier is not None:
        await _wait_for_start_barrier(*start_barrier, deadline=deadline)
    event_loop_lag = EventLoopLagTracker()
    event_loop_lag.start()
    try:
        measurement_results, elapsed, burst_results = await _run_clients(
            client,
            config,
            client_count,
            duration_seconds=config.duration_seconds,
            collect=True,
            max_runtime_deadline=deadline,
        )
    finally:
        await event_loop_lag.stop()
    if time.perf_counter() >= deadline:
        raise ProbeError("runtime_cap", "probe reached its maximum runtime before the final corpus snapshot")
    final_snapshot = await client.snapshot()
    summary: dict[str, OperationSummary] = defaultdict(OperationSummary)
    for result in measurement_results:
        summary[result.operation].add(result)
    operations: dict[str, dict[str, Any]] = {}
    for operation, operation_summary in sorted(summary.items()):
        operation_payload = operation_summary.as_dict()
        operation_payload["throughput_completed_per_second"] = (
            round(operation_summary.completed / config.duration_seconds, 4) if config.duration_seconds else None
        )
        operations[operation] = operation_payload
    burst_summary = OperationSummary()
    for result in burst_results:
        burst_summary.add(result)
    total_failed = sum(item.failed for item in summary.values())
    total_timed_out = sum(item.timed_out for item in summary.values())
    state_unchanged = post_warmup_snapshot == final_snapshot and (
        config.lane != "fixed" or starting_snapshot == post_warmup_snapshot
    )
    eligibility_reasons: list[str] = []
    if config.lane != "fixed":
        eligibility_reasons.append("growth lane is descriptive, not a fixed-work overhead comparison")
    if total_failed:
        eligibility_reasons.append("one or more measured operations failed")
    if total_timed_out:
        eligibility_reasons.append("one or more measured operations timed out")
    if config.lane == "fixed" and not state_unchanged:
        eligibility_reasons.append("fixed-corpus state or fingerprint changed")
    return {
        "clients": client_count,
        "warmup": {"duration_seconds": config.warmup_seconds, "excluded_samples": len(warmup_results)},
        "measurement_seconds": config.duration_seconds,
        "drain_seconds": round(max(0.0, elapsed - config.duration_seconds), 6),
        "attempted": sum(item.attempted for item in summary.values()),
        "completed": sum(item.completed for item in summary.values()),
        "failed": sum(item.failed for item in summary.values()),
        "timed_out": sum(item.timed_out for item in summary.values()),
        "throughput_completed_per_second": round(
            sum(item.completed for item in summary.values()) / config.duration_seconds, 4
        )
        if config.duration_seconds
        else None,
        "simultaneous_burst": burst_summary.as_dict(),
        "event_loop_lag": event_loop_lag.snapshot(),
        "eligibility": {
            "fixed_overhead_comparison": not eligibility_reasons,
            "reasons": eligibility_reasons,
        },
        "operations": operations,
        "corpus": {
            "starting": {
                "memory_rows": starting_snapshot.memory_count,
                "vector_rows": starting_snapshot.vector_count,
                "fingerprint": starting_snapshot.fingerprint,
            },
            "post_warmup": {
                "memory_rows": post_warmup_snapshot.memory_count,
                "vector_rows": post_warmup_snapshot.vector_count,
                "fingerprint": post_warmup_snapshot.fingerprint,
            },
            "final": {
                "memory_rows": final_snapshot.memory_count,
                "vector_rows": final_snapshot.vector_count,
                "fingerprint": final_snapshot.fingerprint,
            },
            "state_unchanged": state_unchanged,
        },
    }


def _sanitized_child_environment(
    data_dir: Path,
    port: int,
    profile: ProviderProfile,
    simulated_base_url: str | None = None,
    rate_limit_rpm: int = 0,
    *,
    source_root: Path = REPOSITORY_ROOT,
    metrics_enabled: bool = False,
) -> dict[str, str]:
    """Construct an explicit child environment with no inherited OC secrets."""
    env = os.environ.copy()
    for key in list(env):
        upper = key.upper()
        if upper.startswith("OC_") or upper in {
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OLLAMA_HOST",
            "OLLAMA_BASE_URL",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        }:
            env.pop(key, None)
    env.update(
        {
            "PYTHONPATH": str(source_root / "src"),
            "OC_DATA_DIR": str(data_dir),
            "OC_DB_PATH": str(data_dir / "openchronicle.db"),
            "OC_CONFIG_DIR": str(data_dir / "config"),
            "OC_OUTPUT_DIR": str(data_dir / "output"),
            "OC_API_HOST": "127.0.0.1",
            "OC_API_PORT": str(port),
            "OC_API_KEY": "",
            "OC_API_ALLOWED_HOSTS": "127.0.0.1:*",
            "OC_MCP_ALLOWED_HOSTS": "127.0.0.1:*",
            "OC_API_RATE_LIMIT_RPM": str(rate_limit_rpm),
            "OC_MAINTENANCE_DISABLED": "1",
            "OC_LOG_FORMAT": "human",
            "OC_METRICS_ENABLED": "true" if metrics_enabled else "false",
        }
    )
    if profile == "none":
        env["OC_EMBEDDING_PROVIDER"] = "none"
    elif profile == "stub":
        env["OC_EMBEDDING_PROVIDER"] = "stub"
        env["OC_EMBEDDING_DIMENSIONS"] = str(VECTOR_DIMENSIONS)
    else:
        if simulated_base_url is None:
            raise ValueError("simulated provider requires a local base URL")
        env.update(
            {
                "OC_EMBEDDING_PROVIDER": "openai",
                "OC_EMBEDDING_MODEL": "probe-simulated",
                "OC_EMBEDDING_DIMENSIONS": str(VECTOR_DIMENSIONS),
                "OC_EMBEDDING_API_KEY": "probe-only",
                "OPENAI_API_KEY": "probe-only",
                "OPENAI_BASE_URL": simulated_base_url,
            }
        )
    return env


@contextmanager
def _running_server(
    config: ProbeConfig,
    data_dir: Path,
    *,
    rate_limit_rpm: int = 0,
) -> Iterator[
    tuple[
        str,
        Callable[[], None],
        int,
        Callable[[], None],
        Callable[[], dict[str, Any]],
    ]
]:
    fake_provider: SimulatedEmbeddingServer | None = None
    if config.provider_profile == "simulated-400ms":
        fake_provider = SimulatedEmbeddingServer()
    port_probe = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = port_probe.server_port
    port_probe.server_close()
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    env = _sanitized_child_environment(
        data_dir,
        port,
        config.provider_profile,
        fake_provider.base_url if fake_provider else None,
        rate_limit_rpm,
        source_root=config.source_root,
        metrics_enabled=config.instrumentation_state == "enabled",
    )
    command = [
        sys.executable,
        "-m",
        "openchronicle.interfaces.cli.main",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(
        command,
        cwd=config.source_root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    scraper: MetricsScraper | None = None
    memory_sampler: ProcessMemorySampler | None = None
    try:
        health_requests = _wait_for_health(base_url, config.request_timeout_seconds, process)
        memory_sampler = ProcessMemorySampler(process.pid)
        if config.scrape_interval_seconds is not None:
            scraper = MetricsScraper(
                base_url,
                config.scrape_interval_seconds,
                min(config.request_timeout_seconds, 5.0),
            )
        memory_sampler.start()
        if scraper is not None:
            scraper.start()

        def enable_measured_provider_delay() -> None:
            if fake_provider is not None:
                fake_provider.set_delay(0.4)

        def reset_measurement_resources() -> None:
            memory_sampler.reset_peak()
            if scraper is not None:
                scraper.reset()

        def resource_snapshot() -> dict[str, Any]:
            return {
                "scrapes": scraper.snapshot() if scraper is not None else None,
                "process_memory": memory_sampler.snapshot(),
            }

        yield base_url, enable_measured_provider_delay, health_requests, reset_measurement_resources, resource_snapshot
    finally:
        try:
            if scraper is not None:
                scraper.stop()
            if memory_sampler is not None:
                memory_sampler.stop()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        if fake_provider is not None:
            fake_provider.close()


def _wait_for_health(base_url: str, timeout_seconds: float, process: subprocess.Popen[bytes]) -> int:
    deadline = time.perf_counter() + min(30.0, max(5.0, timeout_seconds * 3))
    last_error: str | None = None
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            raise ProbeError("startup", "disposable OC server exited before health became ready")
        try:
            transport = RestTransport(base_url, min(timeout_seconds, 1.0))
            result, body = transport.request("GET", "/health")
            if result.completed and body == {"status": "ok"}:
                return 1
            last_error = "health response was not ready"
        except ProbeError, OSError, urllib.error.URLError:
            last_error = "health request failed"
        time.sleep(0.05)
    raise ProbeError("startup_timeout", last_error or "health did not become ready")


def _run_rate_limit_check(config: ProbeConfig, data_dir: Path, deadline: float) -> dict[str, Any]:
    """Exercise the production limiter in its own disposable scenario."""
    # The limiter is shared by REST and MCP; REST avoids adding MCP session
    # setup to this small correctness check.
    transport_name: TransportName = "rest"
    check_config = ProbeConfig(
        transport=transport_name,
        lane="fixed",
        mode="keyword",
        provider_profile="none",
        corpus_size=1,
        clients=(1,),
        warmup_seconds=0.0,
        duration_seconds=1.0,
        request_timeout_seconds=min(config.request_timeout_seconds, 3.0),
        max_runtime_seconds=config.max_runtime_seconds,
        seed=config.seed,
        instrumentation_state=config.instrumentation_state,
        source_root=config.source_root,
    )
    rpm = 600
    with _running_server(check_config, data_dir, rate_limit_rpm=rpm) as (
        base_url,
        _,
        health_requests,
        _,
        _,
    ):
        transport = RestTransport(base_url, check_config.request_timeout_seconds)
        statuses: Counter[str] = Counter()
        remaining = rpm - health_requests
        for _ in range(remaining + 1):
            if time.perf_counter() >= deadline:
                raise ProbeError("runtime_cap", "probe reached its maximum runtime during rate-limit check")
            result, _ = transport.request("GET", "/health")
            statuses[str(result.status_code)] += 1
        expected = {"200": remaining, "429": 1}
        if dict(statuses) != expected:
            raise ProbeError("rate_limit_check", "disposable limiter did not produce the expected bounded 429")
    return {
        "rpm": rpm,
        "health_requests_before_check": health_requests,
        "requests_sent": sum(statuses.values()),
        "status_counts": dict(sorted(statuses.items())),
        "passed": True,
    }


async def _run_case(config: ProbeConfig, data_dir: Path, deadline: float) -> dict[str, Any]:
    case_results = []
    for client_count in config.clients:
        case_dir = data_dir / f"clients-{client_count}"
        with _running_server(config, case_dir) as (
            base_url,
            enable_measured_provider_delay,
            _,
            reset_measurement_resources,
            resource_snapshot,
        ):
            client = WorkloadClient(config, base_url)
            await client.setup(deadline)
            # Seeding uses zero-delay local embeddings; only measured
            # operations pay the simulated 400 ms provider delay.
            enable_measured_provider_delay()
            reset_measurement_resources()
            start_barrier = (
                (config.start_barrier_dir, config.start_barrier_label)
                if config.start_barrier_dir is not None and config.start_barrier_label is not None
                else None
            )
            result = await run_client_count(client, config, client_count, deadline, start_barrier=start_barrier)
            resources = resource_snapshot()
            if resources["scrapes"] is not None:
                result["scrapes"] = resources["scrapes"]
            result["process_memory"] = resources["process_memory"]
            case_results.append(result)
    return {"client_counts": case_results}


def _same_run_configs(config: ProbeConfig, baseline_source_root: Path) -> dict[str, ProbeConfig]:
    """Build the A/B/C conditions for one synchronized REST matrix."""
    return {
        "A": replace(
            config,
            source_root=baseline_source_root,
            instrumentation_state="uninstrumented",
            scrape_interval_seconds=None,
        ),
        "B": replace(config, instrumentation_state="disabled", scrape_interval_seconds=None),
        "C": replace(config, instrumentation_state="enabled"),
    }


def _same_run_affinity_masks(labels: Sequence[str], *, logical_cpu_count: int | None = None) -> dict[str, int]:
    """Assign equal, rotating CPU partitions to the three matrix conditions."""
    if len(labels) != 3:
        raise ProbeError("affinity", "same-run resource isolation requires exactly three conditions")
    available = logical_cpu_count if logical_cpu_count is not None else os.cpu_count()
    required = SAME_RUN_AFFINITY_CPUS_PER_CONDITION * len(labels)
    if available is None or available < required:
        raise ProbeError("affinity", f"same-run resource isolation requires at least {required} logical CPUs")
    width = SAME_RUN_AFFINITY_CPUS_PER_CONDITION
    return {
        label: sum(1 << (position * width + offset) for offset in range(width)) for position, label in enumerate(labels)
    }


def _terminate_matrix_process(process: subprocess.Popen[bytes]) -> None:
    """Stop one matrix child and its disposable server if cleanup needs a fallback."""
    if process.poll() is not None:
        return
    if platform.system() == "Windows":
        with suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        return
    process.terminate()


def _run_same_run_matrix(
    configs: dict[str, ProbeConfig],
    data_dir: Path,
    deadline: float,
    *,
    cpu_affinity_masks: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Run independent probe processes with one post-warm-up start barrier."""
    labels = tuple(configs)
    client_count = configs[labels[0]].clients[0]
    barrier_dir = data_dir / "start-barrier"
    barrier_dir.mkdir(parents=True, exist_ok=True)
    processes: dict[str, subprocess.Popen[bytes]] = {}
    report_paths: dict[str, Path] = {}
    start_released = False
    try:
        for label in labels:
            remaining = deadline - time.perf_counter()
            if remaining <= 1.0:
                raise ProbeError("runtime_cap", "matrix reached its maximum runtime before all children started")
            child_config = configs[label]
            if cpu_affinity_masks is not None:
                child_config = replace(child_config, cpu_affinity_mask=cpu_affinity_masks[label])
            report_path = data_dir / f"{label}.json"
            report_paths[label] = report_path
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source-root",
                str(child_config.source_root),
                "--transport",
                child_config.transport,
                "--lane",
                child_config.lane,
                "--mode",
                child_config.mode,
                "--provider-profile",
                child_config.provider_profile,
                "--corpus-size",
                str(child_config.corpus_size),
                "--clients",
                str(client_count),
                "--warmup-seconds",
                str(child_config.warmup_seconds),
                "--duration-seconds",
                str(child_config.duration_seconds),
                "--request-timeout-seconds",
                str(child_config.request_timeout_seconds),
                "--max-runtime-seconds",
                str(min(child_config.max_runtime_seconds, remaining)),
                "--seed",
                str(child_config.seed),
                "--instrumentation-state",
                child_config.instrumentation_state,
                "--start-barrier-dir",
                str(barrier_dir),
                "--start-barrier-label",
                label,
                "--out",
                str(report_path),
            ]
            if child_config.scrape_interval_seconds is not None:
                command.extend(["--scrape-interval-seconds", str(child_config.scrape_interval_seconds)])
            if child_config.cpu_affinity_mask is not None:
                command.extend(["--cpu-affinity-mask", hex(child_config.cpu_affinity_mask)])
            processes[label] = subprocess.Popen(
                command,
                cwd=REPOSITORY_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Let each child finish its disposable-server setup before starting
            # the next child. The measurement still begins on one shared
            # barrier, but concurrent SQLite seeding/server startup is avoided.
            ready_path = barrier_dir / f"{label}.ready"
            while not ready_path.exists():
                exited_label = next(
                    (existing_label for existing_label, process in processes.items() if process.poll() is not None),
                    None,
                )
                if exited_label is not None:
                    raise ProbeError("matrix_child", "a matrix child exited before reaching the shared start")
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise ProbeError(
                        "barrier_timeout", "matrix children did not reach the shared start before the runtime cap"
                    )
                time.sleep(min(0.05, remaining))
        (barrier_dir / "start").write_text("start\n", encoding="utf-8")
        start_released = True

        while True:
            if all(process.poll() == 0 for process in processes.values()):
                break
            if any(process.poll() not in (None, 0) for process in processes.values()):
                raise ProbeError("matrix_child", "a matrix child failed during the synchronized run")
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise ProbeError("runtime_cap", "matrix reached its maximum runtime while waiting for children")
            time.sleep(min(0.05, remaining))

        reports: dict[str, Any] = {}
        for label in labels:
            try:
                child_report = json.loads(report_paths[label].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProbeError("matrix_report", "a matrix child did not produce a valid report") from exc
            if not isinstance(child_report, dict) or "result" not in child_report:
                raise ProbeError("matrix_report", "a matrix child report was incomplete")
            reports[label] = child_report
        return {
            "mode": "process_side_by_side_file_barrier",
            "condition_order": list(labels),
            "shared_start": "post-warmup readiness markers released by one coordinator",
            "resource_isolation": (
                {
                    "kind": "equal_rotating_cpu_partitions",
                    "logical_cpus_per_condition": SAME_RUN_AFFINITY_CPUS_PER_CONDITION,
                    "masks": {label: hex(mask) for label, mask in cpu_affinity_masks.items()},
                }
                if cpu_affinity_masks is not None
                else None
            ),
            "conditions": reports,
        }
    finally:
        if not start_released and processes:
            with suppress(OSError):
                (barrier_dir / "abort").write_text("abort\n", encoding="utf-8")
        cleanup_deadline = time.perf_counter() + 10.0
        for process in processes.values():
            while process.poll() is None and time.perf_counter() < cleanup_deadline:
                time.sleep(0.05)
            if process.poll() is None:
                _terminate_matrix_process(process)
        for process in processes.values():
            with suppress(OSError, subprocess.SubprocessError):
                process.wait(timeout=2)


def _metadata(config: ProbeConfig) -> dict[str, Any]:
    working_tree_dirty: bool | None = None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=config.source_root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except OSError, subprocess.SubprocessError:
        commit = "unknown"
    with suppress(OSError, subprocess.SubprocessError):
        working_tree_dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=config.source_root,
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()
        )
    return {
        "probe_version": 3,
        "commit": commit,
        "working_tree_dirty": working_tree_dirty,
        "source_state": (
            "dirty-working-tree"
            if working_tree_dirty
            else "clean-working-tree"
            if working_tree_dirty is False
            else "unknown"
        ),
        "package_version": package_version(),
        "dependency_versions": _dependency_versions(),
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "host_class": f"{platform.system().lower()}-{platform.machine().lower()}",
        "transport": config.transport,
        "lane": config.lane,
        "mode": config.mode,
        "provider_profile": config.provider_profile,
        "instrumentation_state": config.instrumentation_state,
        "corpus_size": config.corpus_size,
        "seed": config.seed,
        "content_size": CONTENT_SIZE,
        "content_size_distribution": {
            "kind": "fixed",
            "characters_per_memory": len(_memory_payload(0, PROJECT_ID, config.seed)["content"]),
        },
        "tags": ["probe", *[f"topic-{index:02d}" for index in range(20)]],
        "projects": "one synthetic project per disposable case",
        "vector_dimensions": VECTOR_DIMENSIONS,
        "query_sequence": "deterministic topic sequence derived from seed and worker id",
        "clients": list(config.clients),
        "warmup_seconds": config.warmup_seconds,
        "duration_seconds": config.duration_seconds,
        "request_timeout_seconds": config.request_timeout_seconds,
        "scrape_interval_seconds": config.scrape_interval_seconds,
        "cpu_affinity_mask": hex(config.cpu_affinity_mask) if config.cpu_affinity_mask is not None else None,
        "rate_limit_override": "OC_API_RATE_LIMIT_RPM=0 (disposable child only)",
        "maintenance": "disabled",
        "started_utc": datetime.now(UTC).isoformat(),
    }


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in ("fastapi", "mcp", "pydantic", "uvicorn"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "unavailable"
    return versions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("rest", "mcp"), default="rest")
    parser.add_argument("--lane", choices=("fixed", "growth"), default="fixed")
    parser.add_argument("--mode", choices=("keyword", "semantic", "hybrid"), default="keyword")
    parser.add_argument("--provider-profile", choices=("none", "stub", "simulated-400ms"), default="none")
    parser.add_argument("--corpus-size", type=int, default=1000)
    parser.add_argument("--clients", type=parse_clients, default=DEFAULT_CLIENTS)
    parser.add_argument("--warmup-seconds", type=float, default=5.0)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--max-runtime-seconds", type=float, default=DEFAULT_MAX_RUNTIME_SECONDS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--check-rate-limit",
        action="store_true",
        help="run the disposable default-limiter correctness scenario before the performance case",
    )
    parser.add_argument(
        "--instrumentation-state",
        choices=("uninstrumented", "disabled", "enabled"),
        default="uninstrumented",
        help="set the disposable child metrics state; use --source-root for a truly uninstrumented revision",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="local checkout to launch for the disposable child (default: current checkout)",
    )
    parser.add_argument(
        "--same-run-baseline-root",
        type=Path,
        default=None,
        help="run a synchronized REST A/B/C matrix using this uninstrumented checkout as condition A",
    )
    parser.add_argument(
        "--same-run-order",
        choices=("A,B,C", "B,C,A", "C,A,B"),
        default="A,B,C",
        help="condition startup order for a same-run matrix; measurement still starts on one shared barrier",
    )
    parser.add_argument(
        "--same-run-resource-isolation",
        action="store_true",
        help="partition equal CPU sets across same-run conditions (requires 24 logical CPUs)",
    )
    parser.add_argument("--start-barrier-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--start-barrier-label", choices=("A", "B", "C"), default=None, help=argparse.SUPPRESS)
    parser.add_argument("--cpu-affinity-mask", type=parse_affinity_mask, default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--scrape-interval-seconds",
        type=float,
        default=None,
        help="optionally scrape the disposable /metrics endpoint at this bounded interval",
    )
    parser.add_argument("--out", type=Path, default=None, help="write sanitized JSON here instead of stdout")
    return parser


def _resolve_source_root(path: Path) -> Path:
    try:
        source_root = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ProbeError("invalid_config", "source-root must be an existing local checkout") from exc
    if not (source_root / "src" / "openchronicle").is_dir():
        raise ProbeError("invalid_config", "source-root must contain src/openchronicle")
    return source_root


def _validate_args(args: argparse.Namespace) -> None:
    if args.corpus_size < 1 or args.corpus_size > 10000:
        raise ProbeError("invalid_config", "corpus-size must be from 1 through 10000")
    if args.warmup_seconds < 0 or args.duration_seconds <= 0:
        raise ProbeError("invalid_config", "warmup must be non-negative and duration must be positive")
    if args.request_timeout_seconds <= 0 or args.max_runtime_seconds <= 0:
        raise ProbeError("invalid_config", "request and maximum-runtime timeouts must be positive")
    if args.max_runtime_seconds > DEFAULT_MAX_RUNTIME_SECONDS:
        raise ProbeError("invalid_config", "maximum runtime cannot exceed the 10-minute Phase 1 cap")
    if args.provider_profile == "none" and args.mode != "keyword":
        raise ProbeError("invalid_config", "provider profile 'none' only supports keyword mode")
    if args.scrape_interval_seconds is not None and args.scrape_interval_seconds < 0.01:
        raise ProbeError("invalid_config", "scrape interval must be at least 0.01 seconds")
    if (args.start_barrier_dir is None) != (args.start_barrier_label is None):
        raise ProbeError("invalid_config", "start barrier directory and label must be provided together")
    if args.same_run_resource_isolation and args.same_run_baseline_root is None:
        raise ProbeError("invalid_config", "same-run resource isolation requires a same-run matrix")
    if args.same_run_baseline_root is not None and args.start_barrier_dir is not None:
        raise ProbeError("invalid_config", "same-run matrix cannot be nested inside a start-barrier child")
    _resolve_source_root(args.source_root)
    if args.same_run_baseline_root is not None:
        if args.transport != "rest":
            raise ProbeError("invalid_config", "same-run matrix currently requires REST transport")
        if args.lane != "fixed":
            raise ProbeError("invalid_config", "same-run matrix requires the fixed lane")
        if len(args.clients) != 1:
            raise ProbeError("invalid_config", "same-run matrix requires exactly one client count")
        if args.scrape_interval_seconds is None:
            raise ProbeError("invalid_config", "same-run matrix requires a scrape interval for condition C")
        _resolve_source_root(args.same_run_baseline_root)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        config = ProbeConfig(
            transport=cast(TransportName, args.transport),
            lane=cast(Lane, args.lane),
            mode=cast(Mode, args.mode),
            provider_profile=cast(ProviderProfile, args.provider_profile),
            corpus_size=args.corpus_size,
            clients=args.clients,
            warmup_seconds=args.warmup_seconds,
            duration_seconds=args.duration_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            max_runtime_seconds=args.max_runtime_seconds,
            seed=args.seed,
            instrumentation_state=args.instrumentation_state,
            source_root=_resolve_source_root(args.source_root),
            scrape_interval_seconds=args.scrape_interval_seconds,
            start_barrier_dir=args.start_barrier_dir.expanduser().resolve() if args.start_barrier_dir else None,
            start_barrier_label=args.start_barrier_label,
            cpu_affinity_mask=args.cpu_affinity_mask,
        )
        _apply_process_affinity(config.cpu_affinity_mask)
        with tempfile.TemporaryDirectory(prefix="oc-performance-probe-", ignore_cleanup_errors=True) as temp_dir:
            deadline = time.perf_counter() + config.max_runtime_seconds
            report = _metadata(config)
            if args.check_rate_limit:
                report["rate_limit_check"] = _run_rate_limit_check(
                    config, Path(temp_dir) / "rate-limit-check", deadline
                )
            if args.same_run_baseline_root is None:
                report["result"] = asyncio.run(_run_case(config, Path(temp_dir), deadline))
            else:
                baseline_source_root = _resolve_source_root(args.same_run_baseline_root)
                condition_configs = _same_run_configs(config, baseline_source_root)
                condition_order = tuple(args.same_run_order.split(","))
                ordered_configs = {label: condition_configs[label] for label in condition_order}
                affinity_masks = _same_run_affinity_masks(condition_order) if args.same_run_resource_isolation else None
                report["matrix"] = _run_same_run_matrix(
                    ordered_configs,
                    Path(temp_dir),
                    deadline,
                    cpu_affinity_masks=affinity_masks,
                )
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.out is None:
            sys.stdout.write(serialized)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(serialized, encoding="utf-8")
            print(f"wrote sanitized report to {args.out}", file=sys.stderr)
        return 0
    except ProbeError as exc:
        print(f"probe failed [{exc.category}]: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("probe interrupted; disposable resources were cleaned up", file=sys.stderr)
        return 130
    except Exception:
        print("probe failed [internal_error]", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
