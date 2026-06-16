"""Mock order adapter for backtest — string action only, no shioaji."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class MockOrderAdapter:
    def __init__(self, api: Any) -> None:
        self._api = api

    def place_ioc_limit(
        self,
        contract: Any,
        *,
        action: str,
        qty: int,
        limit_price: float,
        account: Any,
        timeout: int = 0,
    ) -> Any:
        if action not in ("Buy", "Sell"):
            raise ValueError(f"action must be 'Buy' or 'Sell', got {action!r}")
        order = SimpleNamespace(
            action=action,
            price=limit_price,
            quantity=qty,
        )
        return self._api.place_order(contract, order, timeout=timeout)


__all__ = ["MockOrderAdapter"]
