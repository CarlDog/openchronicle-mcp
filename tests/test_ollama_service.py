"""Tests for Ollama model discovery service and CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from openchronicle.core.application.services.ollama_service import (
    ConfigDiff,
    OllamaModelInfo,
    OllamaService,
    _sanitize_filename,
)

# ── Filename sanitization ────────────────────────────────────────────


class TestSanitizeFilename:
    def test_simple_model(self) -> None:
        assert _sanitize_filename("flux") == "ollama_flux.json"

    def test_model_with_tag(self) -> None:
        assert _sanitize_filename("mistral:instruct") == "ollama_mistral_instruct.json"

    def test_model_with_namespace(self) -> None:
        assert _sanitize_filename("HammerAI/mythomax-l2:latest") == "ollama_hammerai_mythomax-l2_latest.json"

    def test_model_with_size_tag(self) -> None:
        assert _sanitize_filename("deepseek-r1:32b") == "ollama_deepseek-r1_32b.json"

    def test_model_with_dots(self) -> None:
        # dots get stripped (not alphanumeric, underscore, or hyphen)
        assert _sanitize_filename("qwen2.5:7b") == "ollama_qwen25_7b.json"


# ── OllamaModelInfo capability inference ─────────────────────────────


class TestModelInfoCapabilities:
    def test_llm_basic(self) -> None:
        info = OllamaModelInfo(
            name="mistral:instruct",
            size_bytes=4_100_000_000,
            parameter_size="7.2B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama"],
            fmt="gguf",
        )
        assert not info.is_diffusion
        assert not info.is_vision
        assert info.inferred_type() == "llm"
        caps = info.inferred_capabilities()
        assert caps["text_generation"] is True
        assert caps["streaming"] is True
        assert caps["function_calling"] is False
        assert caps["vision"] is False

    def test_llm_with_tools(self) -> None:
        info = OllamaModelInfo(
            name="mistral:instruct",
            size_bytes=0,
            parameter_size="7.2B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama"],
            fmt="gguf",
            has_tools=True,
        )
        caps = info.inferred_capabilities()
        assert caps["function_calling"] is True

    def test_vision_model(self) -> None:
        info = OllamaModelInfo(
            name="llava:latest",
            size_bytes=4_700_000_000,
            parameter_size="7B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama", "clip"],
            fmt="gguf",
        )
        assert not info.is_diffusion
        assert info.is_vision
        assert info.inferred_type() == "llm"
        caps = info.inferred_capabilities()
        assert caps["vision"] is True

    def test_diffusion_safetensors(self) -> None:
        info = OllamaModelInfo(
            name="x/flux2-klein:latest",
            size_bytes=5_700_000_000,
            parameter_size="8.0B",
            quantization_level="FP4",
            family="Flux2KleinPipeline",
            families=[],
            fmt="safetensors",
        )
        assert info.is_diffusion
        assert not info.is_vision
        assert info.inferred_type() == "media"
        caps = info.inferred_capabilities()
        assert caps == {"image_generation": True}

    def test_diffusion_by_family(self) -> None:
        info = OllamaModelInfo(
            name="stable-diffusion:latest",
            size_bytes=0,
            parameter_size="",
            quantization_level="",
            family="stable-diffusion",
            families=[],
            fmt="gguf",
        )
        assert info.is_diffusion

    def test_display_name(self) -> None:
        info = OllamaModelInfo(
            name="deepseek-r1:32b",
            size_bytes=0,
            parameter_size="32B",
            quantization_level="Q4_K_M",
            family="qwen2",
            families=["qwen2"],
            fmt="gguf",
        )
        assert info.display_name() == "Ollama - Deepseek R1 32b"

    def test_display_name_latest_tag(self) -> None:
        info = OllamaModelInfo(
            name="llava:latest",
            size_bytes=0,
            parameter_size="7B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama", "clip"],
            fmt="gguf",
        )
        # "latest" tag should be omitted from display name
        assert info.display_name() == "Ollama - Llava"

    def test_description(self) -> None:
        info = OllamaModelInfo(
            name="phi4:14b",
            size_bytes=0,
            parameter_size="14B",
            quantization_level="Q4_0",
            family="phi3",
            families=["phi3"],
            fmt="gguf",
        )
        desc = info.description()
        assert "phi4:14b" in desc
        assert "14B" in desc
        assert "Q4_0" in desc


# ── OllamaService (with mocked HTTP) ────────────────────────────────


def _mock_tags_response() -> dict[str, Any]:
    return {
        "models": [
            {
                "name": "mistral:instruct",
                "size": 4_100_000_000,
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "families": ["llama"],
                    "parameter_size": "7.2B",
                    "quantization_level": "Q4_0",
                },
            },
            {
                "name": "x/flux2-klein:latest",
                "size": 5_700_000_000,
                "details": {
                    "format": "safetensors",
                    "family": "Flux2KleinPipeline",
                    "families": None,
                    "parameter_size": "8.0B",
                    "quantization_level": "FP4",
                },
            },
        ],
    }


def _mock_show_response(name: str) -> dict[str, Any]:
    if "flux" in name:
        return {
            "details": {
                "format": "safetensors",
                "family": "Flux2KleinPipeline",
                "families": None,
                "parameter_size": "8.0B",
                "quantization_level": "FP4",
            },
            "model_info": {},
            "template": "",
        }
    return {
        "details": {
            "format": "gguf",
            "family": "llama",
            "families": ["llama"],
            "parameter_size": "7.2B",
            "quantization_level": "Q4_0",
        },
        "model_info": {
            "llama.context_length": 32768,
        },
        "template": "[AVAILABLE_TOOLS] {{ $.Tools }}[/AVAILABLE_TOOLS][INST]{{ .Content }}[/INST][TOOL_CALLS]",
    }


class TestOllamaServiceListModels:
    def test_list_models(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_tags_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            svc = OllamaService(base_url="http://localhost:11434")
            models = svc.list_models()

        assert len(models) == 2
        assert models[0].name == "mistral:instruct"
        assert models[0].fmt == "gguf"
        assert models[1].name == "x/flux2-klein:latest"
        assert models[1].fmt == "safetensors"

    def test_list_models_empty(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            svc = OllamaService()
            models = svc.list_models()

        assert models == []


class TestOllamaServiceShowModel:
    def test_show_llm(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_show_response("mistral:instruct")
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            svc = OllamaService()
            info = svc.show_model("mistral:instruct")

        assert info.context_length == 32768
        assert info.has_tools is True
        assert info.inferred_type() == "llm"

    def test_show_diffusion(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_show_response("x/flux2-klein:latest")
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            svc = OllamaService()
            info = svc.show_model("x/flux2-klein:latest")

        assert info.is_diffusion
        assert info.inferred_type() == "media"


class TestOllamaServiceDiff:
    def test_diff_no_configs(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"

        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_tags_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            svc = OllamaService()
            diff = svc.diff(models_dir)

        assert len(diff.installed) == 2
        assert len(diff.unconfigured) == 2
        assert diff.configured == []
        assert diff.stale == []

    def test_diff_with_existing_config(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        config = {"provider": "ollama", "model": "mistral:instruct"}
        (models_dir / "ollama_mistral_instruct.json").write_text(json.dumps(config))

        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_tags_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            svc = OllamaService()
            diff = svc.diff(models_dir)

        assert len(diff.unconfigured) == 1
        assert diff.unconfigured[0].name == "x/flux2-klein:latest"
        assert "mistral:instruct" in diff.configured

    def test_diff_stale_config(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        config = {"provider": "ollama", "model": "removed-model:latest"}
        (models_dir / "ollama_removed_model_latest.json").write_text(json.dumps(config))

        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_tags_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            svc = OllamaService()
            diff = svc.diff(models_dir)

        assert "removed-model:latest" in diff.stale


class TestOllamaServiceConfigGeneration:
    def test_generate_llm_config(self) -> None:
        info = OllamaModelInfo(
            name="mistral:instruct",
            size_bytes=4_100_000_000,
            parameter_size="7.2B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama"],
            fmt="gguf",
            context_length=32768,
            has_tools=True,
        )
        svc = OllamaService(base_url="http://localhost:11434")
        config = svc.generate_config(info)

        assert config["provider"] == "ollama"
        assert config["model"] == "mistral:instruct"
        assert config["type"] == "llm"
        assert config["capabilities"]["text_generation"] is True
        assert config["capabilities"]["function_calling"] is True
        assert config["api_config"]["endpoint"] == "http://localhost:11434/api/chat"
        assert config["limits"]["context_window"] == 32768
        assert config["cost_tracking"]["input_cost_per_1k"] == 0.0

    def test_generate_media_config(self) -> None:
        info = OllamaModelInfo(
            name="x/flux2-klein:latest",
            size_bytes=5_700_000_000,
            parameter_size="8.0B",
            quantization_level="FP4",
            family="Flux2KleinPipeline",
            families=[],
            fmt="safetensors",
        )
        svc = OllamaService(base_url="http://localhost:11434")
        config = svc.generate_config(info)

        assert config["type"] == "media"
        assert config["capabilities"] == {"image_generation": True}
        assert config["api_config"]["endpoint"] == "http://localhost:11434/api/generate"
        # Media models shouldn't have cost_tracking or limits
        assert "cost_tracking" not in config
        assert "limits" not in config

    def test_write_config(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        info = OllamaModelInfo(
            name="phi4:14b",
            size_bytes=0,
            parameter_size="14B",
            quantization_level="Q4_0",
            family="phi3",
            families=["phi3"],
            fmt="gguf",
            context_length=16384,
        )
        svc = OllamaService()
        path = svc.write_config(info, models_dir)

        assert path.name == "ollama_phi4_14b.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["model"] == "phi4:14b"
        assert data["provider"] == "ollama"

    def test_remove_config(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        config = {"provider": "ollama", "model": "phi4:14b"}
        config_path = models_dir / "ollama_phi4_14b.json"
        config_path.write_text(json.dumps(config))

        svc = OllamaService()
        removed = svc.remove_config("phi4:14b", models_dir)

        assert removed == config_path
        assert not config_path.exists()

    def test_remove_config_not_found(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        svc = OllamaService()
        removed = svc.remove_config("nonexistent:latest", models_dir)

        assert removed is None


# ── CLI command tests ────────────────────────────────────────────────


class TestOllamaCliCommands:
    """Test CLI dispatch and basic command behavior."""

    def _make_args(self, **kwargs: Any) -> MagicMock:
        args = MagicMock()
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def _make_container(self, tmp_path: Path) -> MagicMock:
        container = MagicMock()
        paths = MagicMock()
        paths.config_dir = tmp_path
        container.paths = paths
        return container

    def test_dispatch_unknown_subcommand(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama

        args = self._make_args(ollama_command="nonexistent")
        container = self._make_container(tmp_path)
        assert cmd_ollama(args, container) == 1

    def test_dispatch_none_subcommand(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama

        args = self._make_args(ollama_command=None)
        container = self._make_container(tmp_path)
        assert cmd_ollama(args, container) == 1

    def test_list_connection_error(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama_list

        args = self._make_args(json_output=False)
        container = self._make_container(tmp_path)

        with patch("openchronicle.interfaces.cli.commands.ollama._make_service") as mock_svc:
            mock_svc.return_value.diff.side_effect = httpx.ConnectError("refused")
            result = cmd_ollama_list(args, container)

        assert result == 1

    def test_add_already_exists(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama_add

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "ollama_mistral_instruct.json").write_text('{"model":"mistral:instruct"}')

        args = self._make_args(model="mistral:instruct", force=False)
        container = self._make_container(tmp_path)

        mock_info = OllamaModelInfo(
            name="mistral:instruct",
            size_bytes=0,
            parameter_size="7.2B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama"],
            fmt="gguf",
        )
        with patch("openchronicle.interfaces.cli.commands.ollama._make_service") as mock_svc:
            mock_svc.return_value.show_model.return_value = mock_info
            result = cmd_ollama_add(args, container)

        assert result == 1

    def test_add_force_overwrites(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama_add

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "ollama_mistral_instruct.json").write_text('{"model":"old"}')

        args = self._make_args(model="mistral:instruct", force=True)
        container = self._make_container(tmp_path)

        mock_info = OllamaModelInfo(
            name="mistral:instruct",
            size_bytes=0,
            parameter_size="7.2B",
            quantization_level="Q4_0",
            family="llama",
            families=["llama"],
            fmt="gguf",
        )
        with patch("openchronicle.interfaces.cli.commands.ollama._make_service") as mock_svc:
            mock_svc.return_value.show_model.return_value = mock_info
            mock_svc.return_value.write_config.return_value = models_dir / "ollama_mistral_instruct.json"
            result = cmd_ollama_add(args, container)

        assert result == 0

    def test_remove_not_found(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama_remove

        args = self._make_args(model="nonexistent:latest")
        container = self._make_container(tmp_path)

        with patch("openchronicle.interfaces.cli.commands.ollama._make_service") as mock_svc:
            mock_svc.return_value.remove_config.return_value = None
            result = cmd_ollama_remove(args, container)

        assert result == 1

    def test_sync_all_configured(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.cli.commands.ollama import cmd_ollama_sync

        args = self._make_args(prune=False)
        container = self._make_container(tmp_path)

        diff = ConfigDiff(installed=[], configured=["mistral:instruct"], unconfigured=[], stale=[])
        with patch("openchronicle.interfaces.cli.commands.ollama._make_service") as mock_svc:
            mock_svc.return_value.diff.return_value = diff
            result = cmd_ollama_sync(args, container)

        assert result == 0
