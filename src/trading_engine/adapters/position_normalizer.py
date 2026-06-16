"""Broker-neutral helpers for normalizing position/order direction.

Shioaji-specific logic is isolated here so core/session/order_executor
never need to import shioaji at runtime.
"""

from __future__ import annotations

from typing import Any


def is_long_direction(direction: Any) -> bool:
    """Return True if direction represents Buy/Long.

    Accepts:
      - str: "Buy", "buy", "BUY", "Sell"...
      - shioaji Action enum (if shioaji is importable)
      - objects with .name == "Buy"
    Falls back gracefully if shioaji not installed.
    """
    if direction is None:
        return False

    # Fast path for common strings (works for mock + shioaji stringified)
    if isinstance(direction, str):
        d = direction.lower()
        if d in ("buy", "long"):
            return True
        if d in ("sell", "short"):
            return False

    # Enum-like or has .name
    name = getattr(direction, "name", None)
    if isinstance(name, str):
        if name.lower() == "buy":
            return True
        if name.lower() == "sell":
            return False

    # Try shioaji only if present (isolated)
    try:
        import shioaji as sj  # noqa: F401

        if direction in (sj.Action.Buy, getattr(sj, "Action", type("x", (), {})).Buy):
            return True
        if direction in (sj.Action.Sell, getattr(sj, "Action", type("x", (), {})).Sell):
            return False
        # Some shioaji objects expose .action or similar
        if getattr(direction, "action", None) in (sj.Action.Buy, "Buy"):
            return True
    except Exception:
        # shioaji not installed or incompatible; rely on previous checks
        pass

    # Last resort stringification
    text = str(direction).lower()
    return "buy" in text or "long" in text


__all__ = ["is_long_direction"]
