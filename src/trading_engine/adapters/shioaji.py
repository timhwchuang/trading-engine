"""Shioaji order adapter — sole module that imports shioaji for order construction."""

from __future__ import annotations

from typing import Any


class ShioajiOrderAdapter:
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
        import shioaji as sj

        order = sj.FuturesOrder(
            action=sj.Action.Buy if action == "Buy" else sj.Action.Sell,
            price=limit_price,
            quantity=qty,
            price_type=sj.FuturesPriceType.LMT,
            order_type=sj.OrderType.IOC,
            octype=sj.FuturesOCType.Auto,
            account=account,
        )
        return self._api.place_order(contract, order, timeout=timeout)


__all__ = ["ShioajiOrderAdapter"]