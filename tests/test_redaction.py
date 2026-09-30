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


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://oluser:p@ssW0rd@ollama.example.com:11434", "https://ollama.example.com:11434"),  # "@" in the password
        (" https://oluser:WHOLESECRET@h:1", "https://h:1"),  # the raw env value, unstripped
        ("https://u:S3 CRET@h", "https://h"),
        ("HTTPS://u:pw@host", "https://host"),
        ("http://u:pw@[::1]:11434", "http://[::1]:11434"),
        ("https://host?u=a@b", "https://host?u=a@b"),  # an "@" in the query is not userinfo
        ("nas:11434?x=a@b", "nas:11434?x=a@b"),
    ],
)
def test_redact_url_userinfo_parses_the_host(url: str, expected: str) -> None:
    assert redact_url_userinfo(url) == expected


def _log_a_chained_http_error() -> None:
    """What add_memory logs when Ollama answers 500: a warning with the
    adapter's error, chained from httpx's, whose text carries the URL. The
    password holds a quote, which JSON escapes."""
    import httpx

    url = 'http://oluser:p@ss"S3CRET@127.0.0.1:11999/api/embed'
    request = httpx.Request("POST", url)
    try:
        try:
            httpx.Response(500, request=request).raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError("embedding provider failed") from exc
    except RuntimeError:
        logging.getLogger("oc.test").warning("Failed to generate embedding for %s", url, exc_info=True)
    for handler in logging.getLogger().handlers:
        handler.flush()


@pytest.mark.parametrize("fmt", ["human", "json"])
def test_the_log_file_never_holds_a_host_credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """Per-call-site redaction kept missing paths: the traceback of a chained
    httpx error carries the full URL. The formatters redact everything."""
    from openchronicle.interfaces.logging_setup import configure_root_logger

    log_path = tmp_path / "oc.log"
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    monkeypatch.setenv("OC_LOG_FORMAT", fmt)
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        configure_root_logger()
        _log_a_chained_http_error()
    finally:
        for handler in root.handlers[:]:
            if handler not in old_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(old_level)
    text = log_path.read_text(encoding="utf-8")
    assert "HTTPStatusError" in text and "127.0.0.1:11999" in text, "premise: the traceback and URL were logged"
    assert "S3CRET" not in text and "oluser" not in text
