"""Credentials in host URLs never reach a log line (OC_LOG_FILE outlives the process)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from openchronicle.core.domain.redaction import redact_url_userinfo


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://oluser:S3CRET@ollama.invalid:11434", "https://ollama.invalid:11434"),
        ("oluser:S3CRET@nas:11434", "nas:11434"),  # OLLAMA_HOST without a scheme
        ("http://nas:11434", "http://nas:11434"),
        ("https://x:ghp_secret@github.com/foo/bar", "https://github.com/foo/bar"),
        ("nas:11434/path@x", "nas:11434/path@x"),  # an "@" after the host is not userinfo
        ("", ""),
    ],
)
def test_redact_url_userinfo(url: str, expected: str) -> None:
    assert redact_url_userinfo(url) == expected


def test_the_tls_warning_names_the_host_without_its_credentials(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

    monkeypatch.setenv("OLLAMA_VERIFY_TLS", "0")
    with caplog.at_level(logging.WARNING):
        OllamaEmbeddingAdapter(host="https://oluser:S3CRET@ollama.invalid:11434")
    assert "OLLAMA_VERIFY_TLS disabled" in caplog.text, "premise: the warning was logged"
    assert "ollama.invalid" in caplog.text
    assert "S3CRET" not in caplog.text and "oluser" not in caplog.text


def test_the_remote_endpoint_warning_names_the_host_without_its_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "oluser:S3CRET@ollama.example.com:11434")
    with caplog.at_level(logging.WARNING):
        container = CoreContainer(db_path=str(tmp_path / "oc.db"), config_dir=str(config_dir))
    container.storage.close()
    assert "REMOTE endpoint" in caplog.text, "premise: the egress warning was logged"
    assert "ollama.example.com" in caplog.text
    assert "S3CRET" not in caplog.text and "oluser" not in caplog.text
