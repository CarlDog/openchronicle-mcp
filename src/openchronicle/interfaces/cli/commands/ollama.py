"""Ollama model management CLI commands.

Discover installed Ollama models, view details, and manage model config
files in the configured config directory.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import httpx

from openchronicle.core.application.services.ollama_service import (
    OllamaService,
    _sanitize_filename,
)
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def cmd_ollama(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to ollama subcommands."""
    ollama_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "list": cmd_ollama_list,
        "show": cmd_ollama_show,
        "add": cmd_ollama_add,
        "remove": cmd_ollama_remove,
        "sync": cmd_ollama_sync,
    }
    handler = ollama_dispatch.get(args.ollama_command)
    if handler is None:
        print("Usage: oc ollama <list|show|add|remove|sync>")
        return 1
    return handler(args, container)


def _make_service() -> OllamaService:
    return OllamaService()


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.0f} MB"
    return f"{size_bytes} B"


def cmd_ollama_list(args: argparse.Namespace, container: CoreContainer) -> int:
    """List installed Ollama models and their config status."""
    svc = _make_service()
    models_dir = container.paths.config_dir / "models"

    try:
        diff = svc.diff(models_dir)
    except httpx.ConnectError:
        print("Error: Cannot connect to Ollama. Is it running?")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Error: Ollama API returned {exc.response.status_code}")
        return 1

    if not diff.installed:
        print("No models installed in Ollama.")
        return 0

    configured_set = set(diff.configured)
    print(f"Config directory: {models_dir}")
    print(
        f"Installed models: {len(diff.installed)}  |  Configured: {len(diff.configured)}  |  Unconfigured: {len(diff.unconfigured)}"
    )
    if diff.stale:
        print(f"Stale configs (model not installed): {len(diff.stale)}")
    print()

    # Header
    print(f"{'Model':<40} {'Size':>8}  {'Params':>8}  {'Quant':<6}  {'Type':<6}  {'Config'}")
    print("-" * 100)

    for m in diff.installed:
        is_diffusion = m.fmt == "safetensors" or any(
            kw in m.family.lower() for kw in ("flux", "stable-diffusion", "sdxl")
        )
        model_type = "media" if is_diffusion else "llm"
        has_config = "yes" if m.name in configured_set else "  -"
        print(
            f"{m.name:<40} {_format_size(m.size_bytes):>8}  "
            f"{m.parameter_size:>8}  {m.quantization_level:<6}  {model_type:<6}  {has_config}"
        )

    if diff.stale:
        print()
        print("Stale configs (no matching installed model):")
        for name in diff.stale:
            print(f"  {name}")

    if args.json_output:
        payload = {
            "installed": [
                {
                    "name": m.name,
                    "size_bytes": m.size_bytes,
                    "parameter_size": m.parameter_size,
                    "configured": m.name in configured_set,
                }
                for m in diff.installed
            ],
            "unconfigured": [m.name for m in diff.unconfigured],
            "stale": diff.stale,
        }
        print()
        print(json.dumps(payload, indent=2))

    return 0


def cmd_ollama_show(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show detailed info for an installed Ollama model."""
    svc = _make_service()

    try:
        info = svc.show_model(args.model)
    except httpx.ConnectError:
        print("Error: Cannot connect to Ollama. Is it running?")
        return 1
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            print(f"Error: Model '{args.model}' not found in Ollama.")
            return 1
        print(f"Error: Ollama API returned {exc.response.status_code}")
        return 1

    caps = info.inferred_capabilities()

    print(f"Model:          {info.name}")
    print(f"Type:           {info.inferred_type()}")
    print(f"Family:         {info.family or '(unknown)'}")
    if info.families:
        print(f"Families:       {', '.join(info.families)}")
    print(f"Format:         {info.fmt}")
    print(f"Parameters:     {info.parameter_size or '(unknown)'}")
    print(f"Quantization:   {info.quantization_level or '(unknown)'}")
    if info.context_length:
        print(f"Context length: {info.context_length:,}")
    print(f"Tool support:   {'yes' if info.has_tools else 'no'}")
    print()
    print("Inferred capabilities:")
    for cap, val in caps.items():
        print(f"  {cap}: {val}")

    # Show what the generated config would look like.
    if args.show_config:
        print()
        print("Generated config:")
        config = svc.generate_config(info)
        print(json.dumps(config, indent=2))

    # Check if config exists.
    models_dir = container.paths.config_dir / "models"
    filename = _sanitize_filename(info.name)
    config_path = models_dir / filename
    print()
    if config_path.exists():
        print(f"Config file: {config_path} (exists)")
    else:
        print(f"Config file: {config_path} (not created)")
        print(f"  Run: oc ollama add {info.name}")

    return 0


def cmd_ollama_add(args: argparse.Namespace, container: CoreContainer) -> int:
    """Create a config file for an installed Ollama model."""
    svc = _make_service()
    models_dir = container.paths.config_dir / "models"

    try:
        info = svc.show_model(args.model)
    except httpx.ConnectError:
        print("Error: Cannot connect to Ollama. Is it running?")
        return 1
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            print(f"Error: Model '{args.model}' not found in Ollama.")
            return 1
        print(f"Error: Ollama API returned {exc.response.status_code}")
        return 1

    filename = _sanitize_filename(info.name)
    config_path = models_dir / filename

    if config_path.exists() and not args.force:
        print(f"Config already exists: {config_path}")
        print("Use --force to overwrite.")
        return 1

    models_dir.mkdir(parents=True, exist_ok=True)
    path = svc.write_config(info, models_dir)
    print(f"Created: {path}")
    print(f"  model: {info.name}")
    print(f"  type: {info.inferred_type()}")
    caps = info.inferred_capabilities()
    print(f"  capabilities: {', '.join(k for k, v in caps.items() if v)}")
    return 0


def cmd_ollama_remove(args: argparse.Namespace, container: CoreContainer) -> int:
    """Remove the config file for an Ollama model."""
    svc = _make_service()
    models_dir = container.paths.config_dir / "models"

    removed = svc.remove_config(args.model, models_dir)
    if removed:
        print(f"Removed: {removed}")
        return 0

    print(f"No config found for model '{args.model}' in {models_dir}")
    return 1


def cmd_ollama_sync(args: argparse.Namespace, container: CoreContainer) -> int:
    """Create configs for all installed models that don't have one."""
    svc = _make_service()
    models_dir = container.paths.config_dir / "models"

    try:
        diff = svc.diff(models_dir)
    except httpx.ConnectError:
        print("Error: Cannot connect to Ollama. Is it running?")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Error: Ollama API returned {exc.response.status_code}")
        return 1

    if not diff.unconfigured:
        print("All installed models already have configs.")
        if diff.stale and args.prune:
            return _prune_stale(svc, diff.stale, models_dir)
        return 0

    models_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for model in diff.unconfigured:
        try:
            info = svc.show_model(model.name)
        except httpx.HTTPStatusError:
            print(f"  Warning: Could not fetch details for {model.name}, skipping.")
            continue
        path = svc.write_config(info, models_dir)
        created.append(f"  {path.name:<45} ({info.name})")

    print(f"Created {len(created)} config(s) in {models_dir}:")
    for line in created:
        print(line)

    if diff.stale and args.prune:
        print()
        return _prune_stale(svc, diff.stale, models_dir)

    if diff.stale:
        print()
        print(f"{len(diff.stale)} stale config(s) remain (use --prune to remove):")
        for name in diff.stale:
            print(f"  {name}")

    return 0


def _prune_stale(svc: OllamaService, stale: list[str], models_dir: Path) -> int:
    """Remove configs for models no longer installed."""
    removed = 0
    for model_name in stale:
        path = svc.remove_config(model_name, models_dir)
        if path:
            print(f"Pruned: {path.name} ({model_name})")
            removed += 1
    print(f"Pruned {removed} stale config(s).")
    return 0
