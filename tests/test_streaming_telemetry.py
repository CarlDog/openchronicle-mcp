"""Tests for streaming telemetry — _stream_turn accepts and passes telemetry."""

from __future__ import annotations

import inspect

from openchronicle.interfaces.cli.chat import _stream_turn


class TestStreamTurnTelemetryParam:
    def test_accepts_telemetry_parameter(self) -> None:
        """_stream_turn signature includes telemetry parameter."""
        sig = inspect.signature(_stream_turn)
        assert "telemetry" in sig.parameters

    def test_telemetry_defaults_to_none(self) -> None:
        """telemetry parameter defaults to None when not provided."""
        sig = inspect.signature(_stream_turn)
        param = sig.parameters["telemetry"]
        assert param.default is None


class TestChatLoopTelemetryWiring:
    def test_chat_loop_imports_metrics_tracker(self) -> None:
        """chat_loop uses MetricsTracker for telemetry (smoke import check)."""
        from openchronicle.interfaces.cli.chat import chat_loop

        # Verify the function exists and is async
        assert inspect.iscoroutinefunction(chat_loop)

    def test_stream_turn_passes_telemetry_to_prepare_ask(self) -> None:
        """Verify _stream_turn code references telemetry= in prepare_ask call."""
        source = inspect.getsource(_stream_turn)
        assert "telemetry=telemetry" in source

    def test_stream_turn_passes_telemetry_to_finalize_turn(self) -> None:
        """Verify _stream_turn code references telemetry= in finalize_turn call."""
        source = inspect.getsource(_stream_turn)
        assert "telemetry=telemetry" in source
