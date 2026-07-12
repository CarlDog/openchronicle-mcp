"""Tests for application.config.settings — fail-soft embedding settings loading.

One bad env var must not crash `oc serve`: under `restart: unless-stopped`
a hard exit becomes a crash loop. The loader degrades to safe defaults
(provider "none" / default timeout) with a warning instead of raising.
"""

from __future__ import annotations

import pytest

from openchronicle.core.application.config.settings import (
    EmbeddingSettings,
    load_embedding_settings,
)

# ---------- fail-soft loading ----------


class TestLoadEmbeddingSettingsFailSoft:
    def test_invalid_provider_env_degrades_to_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "definitely-not-a-provider")
        with caplog.at_level("WARNING"):
            settings = load_embedding_settings()
        assert settings.provider == "none"
        assert any("Unknown embedding provider" in r.message for r in caplog.records)

    def test_invalid_provider_file_value_degrades_to_none(self) -> None:
        settings = load_embedding_settings({"provider": "bogus"})
        assert settings.provider == "none"

    def test_unparseable_timeout_env_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_TIMEOUT", "not-a-number")
        assert load_embedding_settings().timeout == 30.0

    def test_non_positive_timeout_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("OC_EMBEDDING_TIMEOUT", "-5")
        with caplog.at_level("WARNING"):
            assert load_embedding_settings().timeout == 30.0
        assert any("Invalid embedding timeout" in r.message for r in caplog.records)
        monkeypatch.setenv("OC_EMBEDDING_TIMEOUT", "0")
        assert load_embedding_settings().timeout == 30.0

    def test_negative_dimensions_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_DIMENSIONS", "-3")
        assert load_embedding_settings().dimensions is None

    def test_unparseable_dimensions_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_DIMENSIONS", "banana")
        assert load_embedding_settings().dimensions is None

    def test_all_env_vars_invalid_still_loads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "???")
        monkeypatch.setenv("OC_EMBEDDING_TIMEOUT", "later")
        monkeypatch.setenv("OC_EMBEDDING_DIMENSIONS", "-1")
        settings = load_embedding_settings()
        assert settings.provider == "none"
        assert settings.timeout == 30.0
        assert settings.dimensions is None


# ---------- valid values still load ----------


class TestLoadEmbeddingSettingsValid:
    def test_valid_env_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "OLLAMA")
        monkeypatch.setenv("OC_EMBEDDING_TIMEOUT", "12.5")
        monkeypatch.setenv("OC_EMBEDDING_DIMENSIONS", "768")
        settings = load_embedding_settings()
        assert settings.provider == "ollama"
        assert settings.timeout == 12.5
        assert settings.dimensions == 768

    def test_defaults_with_no_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in (
            "OC_EMBEDDING_PROVIDER",
            "OC_EMBEDDING_TIMEOUT",
            "OC_EMBEDDING_DIMENSIONS",
        ):
            monkeypatch.delenv(var, raising=False)
        settings = load_embedding_settings()
        assert settings.provider == "none"
        assert settings.timeout == 30.0
        assert settings.dimensions is None


# ---------- direct construction stays strict ----------


class TestEmbeddingSettingsValidation:
    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="embedding provider"):
            EmbeddingSettings(provider="bogus")

    def test_non_positive_timeout_raises(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            EmbeddingSettings(timeout=0)

    def test_invalid_dimensions_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensions"):
            EmbeddingSettings(dimensions=0)
