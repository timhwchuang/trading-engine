"""Order adapter protocol: the only seam for IOC limit order construction."""

from __future__ import annotations

from typing import Any, Protocol


class OrderAdapter(Protocol):
    def place_ioc_limit(
        self,
        contract: Any,
        *,
        action: str,
        qty: int,
        limit_price: float,
        account: Any,
        timeout: int = 0,
    ) -> Any: ...


__all__ = ["OrderAdapter"]