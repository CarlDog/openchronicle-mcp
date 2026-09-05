"""Artifact framing rejects corruption that syntactically valid JSON hides."""

import json

import pytest

from scripts.probe_artifact import PREFIX, decode, encode, load_json


def _payload() -> bytes:
    return json.dumps({"sample": "x" * 9000, "count": 123, "unicode": "é"}).encode()


def test_timestamped_out_of_order_log_records_round_trip() -> None:
    payload = _payload()
    records = encode(payload)
    assert all(len(record) < 3000 for record in records)
    logs = "unrelated progress\n" + "\n".join("2026-09-05T16:28:37.791171084Z " + line for line in reversed(records))
    assert decode(logs) == payload


@pytest.mark.parametrize("problem", ["missing", "duplicate", "split", "timestamp", "checksum", "header", "index"])
def test_damaged_transport_fails_closed(problem: str) -> None:
    records = encode(_payload())
    if problem == "missing":
        records.pop()
    elif problem == "duplicate":
        records.append(records[0])
    elif problem == "split":
        records[0] = records[0][:200] + "\n" + records[0][200:]
    elif problem == "timestamp":
        records[0] = records[0][:200] + "2026-09-05T16:28:37.791171084Z " + records[0][200:]
    elif problem == "checksum":
        fields = records[0].split()
        fields[-1] = "Y" + fields[-1][1:]
        records[0] = " ".join(fields)
    elif problem == "header":
        records[0] = records[0].replace("/5", "/6", 1)
    else:
        records[0] = records[0].replace(PREFIX + "1/", PREFIX + "0/", 1)
    with pytest.raises(ValueError):
        decode("\n".join(records))


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b"[]"])
def test_invalid_json_contract_is_rejected(payload: bytes) -> None:
    with pytest.raises(ValueError):
        load_json(payload)


def test_non_boundary_marker_and_empty_logs_fail() -> None:
    with pytest.raises(ValueError, match="boundary"):
        decode("prefix " + encode(_payload())[0])
    with pytest.raises(ValueError, match="missing"):
        decode("no records")
