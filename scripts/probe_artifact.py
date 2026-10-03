"""Checksummed, bounded transport for disposable benchmark reports.

Prefer copying the report file from the stopped container. When only logs
are available, emit short numbered base64 records instead of a giant JSON
line. Docker timestamps are permitted only at record boundaries. This is
integrity checking, not authentication of an untrusted producer.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from pathlib import Path
from typing import Any

PREFIX = "OC_BENCHMARK_ARTIFACT_V1 "
CHUNK_BYTES = 2048
MAX_BYTES = 2 * 1024 * 1024
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ")
RECORD = re.compile(r"(\d+)/(\d+) (\d+) ([0-9a-f]{64}) ([A-Za-z0-9+/=]+)")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def load_json(payload: bytes) -> dict[str, Any]:
    """Reject duplicate keys, non-finite values, and non-object documents."""
    if not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("artifact exceeds size bound or is empty")
    value = json.loads(payload, object_pairs_hook=_object, parse_constant=_constant)
    # json.loads also accepts overflowing exponents such as 1e999.
    json.dumps(value, allow_nan=False)
    if not isinstance(value, dict):
        raise ValueError("artifact must be a JSON object")
    return value


def encode(payload: bytes) -> list[str]:
    load_json(payload)
    digest = hashlib.sha256(payload).hexdigest()
    count = (len(payload) + CHUNK_BYTES - 1) // CHUNK_BYTES
    return [
        f"{PREFIX}{index + 1}/{count} {len(payload)} {digest} "
        + base64.b64encode(payload[start : start + CHUNK_BYTES]).decode("ascii")
        for index, start in enumerate(range(0, len(payload), CHUNK_BYTES))
    ]


def decode(logs: str) -> bytes:
    """Reassemble exactly one artifact; incomplete/mixed/duplicate logs fail."""
    if len(logs.encode("utf-8")) > MAX_BYTES * 3:
        raise ValueError("log input exceeds size bound")
    header: tuple[int, int, str] | None = None
    chunks: dict[int, bytes] = {}
    for line in logs.splitlines():
        line = TIMESTAMP.sub("", line, count=1)
        if not line.startswith(PREFIX):
            if PREFIX in line:
                raise ValueError("artifact marker outside record boundary")
            continue
        match = RECORD.fullmatch(line[len(PREFIX) :])
        if match is None:
            raise ValueError("malformed or split artifact record")
        index, count, size = (int(match[number]) for number in (1, 2, 3))
        if not 0 < size <= MAX_BYTES or count != (size + CHUNK_BYTES - 1) // CHUNK_BYTES or not 1 <= index <= count:
            raise ValueError("invalid artifact size or chunk index")
        current = count, size, match[4]
        if header is not None and header != current:
            raise ValueError("mixed artifact headers")
        header = current
        if index in chunks:
            raise ValueError("duplicate artifact chunk")
        try:
            chunk = base64.b64decode(match[5], validate=True)
        except binascii.Error as exc:
            raise ValueError("invalid artifact encoding") from exc
        expected_size = CHUNK_BYTES if index < count else size - CHUNK_BYTES * (count - 1)
        if len(chunk) != expected_size:
            raise ValueError("incorrect artifact chunk length")
        chunks[index] = chunk
    if header is None or len(chunks) != header[0]:
        raise ValueError("missing artifact chunks")
    payload = b"".join(chunks[index] for index in range(1, header[0] + 1))
    if len(payload) != header[1] or hashlib.sha256(payload).hexdigest() != header[2]:
        raise ValueError("artifact checksum mismatch")
    load_json(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.logs.stat().st_size > MAX_BYTES * 3:
            raise ValueError("log input exceeds size bound")
        payload = decode(args.logs.read_text(encoding="utf-8"))
        # Decode verifies transport; the consumer must also verify semantics.
        from scripts.probe_sequential import validate_report

        validate_report(load_json(payload))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("xb") as output:
            output.write(payload)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Artifact rejected: {exc}\n")
    print(f"Verified {len(payload)} bytes sha256={hashlib.sha256(payload).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
