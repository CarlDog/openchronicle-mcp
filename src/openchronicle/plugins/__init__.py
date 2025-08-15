from typing import Protocol, Dict, Any


class Registers(Protocol):
    def register(self, container: Dict[str, Any]) -> None: ...


def load_plugin(mode: str):
    if mode == "storytelling":
        # import deferred to avoid hard dependency if plugin is missing
        try:
            from .storytelling import plugin as storytelling_plugin  # type: ignore
            return storytelling_plugin
        except Exception:
            return None
    return None
