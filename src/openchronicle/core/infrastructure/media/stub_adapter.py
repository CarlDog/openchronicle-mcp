"""Deterministic stub media generation adapter for testing."""

from __future__ import annotations

import hashlib
import struct
import time

from openchronicle.core.domain.models.media import MediaRequest, MediaResult
from openchronicle.core.domain.ports.media_generation_port import MediaGenerationPort

# Minimal valid 1x1 PNG (67 bytes) — used as a template
_MINIMAL_PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR"  # IHDR chunk
    b"\x00\x00\x00\x01"  # width=1
    b"\x00\x00\x00\x01"  # height=1
    b"\x08\x02"  # 8-bit RGB
    b"\x00\x00\x00"  # compression, filter, interlace
)


class StubMediaAdapter(MediaGenerationPort):
    """Deterministic media generation — no external calls.

    Generates a small valid PNG whose pixel colour is derived from the
    prompt hash.  Useful for unit tests and as the default when no
    provider is configured.
    """

    def __init__(self, model: str = "stub-media") -> None:
        self._model = model

    def generate(self, request: MediaRequest) -> MediaResult:
        t0 = time.perf_counter()
        digest = hashlib.sha256(request.prompt.encode()).digest()

        # Derive a deterministic seed from the prompt if none provided
        seed = request.seed
        if seed is None:
            seed = struct.unpack(">I", digest[:4])[0]

        # Build a tiny PNG with prompt-derived colour
        data = self._build_png(digest)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return MediaResult(
            data=data,
            media_type=request.media_type,
            mime_type="image/png",
            width=1,
            height=1,
            model=self._model,
            provider="stub",
            seed=seed,
            latency_ms=elapsed_ms,
            metadata={"prompt_hash": digest.hex()[:16]},
        )

    def supported_media_types(self) -> list[str]:
        return ["image"]

    def model_name(self) -> str:
        return self._model

    @staticmethod
    def _build_png(digest: bytes) -> bytes:
        """Build a minimal valid 1x1 PNG with colour from *digest*."""
        import io
        import zlib

        r, g, b = digest[0], digest[1], digest[2]
        # IDAT: filter-byte 0 + RGB
        raw_data = bytes([0, r, g, b])
        compressed = zlib.compress(raw_data)

        buf = io.BytesIO()

        def _write_chunk(chunk_type: bytes, chunk_data: bytes) -> None:
            import struct as _struct

            buf.write(_struct.pack(">I", len(chunk_data)))
            buf.write(chunk_type)
            buf.write(chunk_data)
            crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            buf.write(_struct.pack(">I", crc))

        # Signature
        buf.write(b"\x89PNG\r\n\x1a\n")
        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        _write_chunk(b"IHDR", ihdr_data)
        # IDAT
        _write_chunk(b"IDAT", compressed)
        # IEND
        _write_chunk(b"IEND", b"")

        return buf.getvalue()
