"""Helper utilities for the storytelling plugin."""

from __future__ import annotations

import hashlib


def hash_text(text: str) -> str:
    """Generate SHA256 hash of text for event tracking."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def format_draft(prompt: str) -> str:
    """Format a narrative draft from the given prompt."""
    return f"[storytelling draft] {prompt}"
