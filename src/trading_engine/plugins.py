"""Strategy plugin discovery via setuptools entry points."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

ENTRY_POINT_GROUP = "trading_engine.strategies"


def load_strategy(name: str, **kwargs: Any):
    """Load a registered strategy plugin by entry point name."""
    eps = entry_points(group=ENTRY_POINT_GROUP)
    for ep in eps:
        if ep.name == name:
            factory = ep.load()
            return factory(**kwargs)
    available = ", ".join(sorted(ep.name for ep in eps)) or "(none)"
    raise LookupError(
        f"Unknown strategy plugin {name!r}. Available: {available}"
    )


__all__ = ["ENTRY_POINT_GROUP", "load_strategy"]