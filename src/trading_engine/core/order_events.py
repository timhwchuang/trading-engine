"""Order event type constants shared by live and mock brokers."""

from __future__ import annotations

from typing import Any

FUTURES_ORDER = "FuturesOrder"
FUTURES_DEAL = "FuturesDeal"


def normalize_order_stat(stat: Any) -> str:
    if isinstance(stat, str):
        return stat
    name = getattr(stat, "name", None)
    if name is not None:
        return str(name)
    return str(stat)


def is_futures_order(stat: Any) -> bool:
    return normalize_order_stat(stat) == FUTURES_ORDER


def is_futures_deal(stat: Any) -> bool:
    return normalize_order_stat(stat) == FUTURES_DEAL


__all__ = [
    "FUTURES_DEAL",
    "FUTURES_ORDER",
    "is_futures_deal",
    "is_futures_order",
    "normalize_order_stat",
]
