"""Broker / market-data port (the seam between TradingEngine and a concrete broker).

This Protocol *documents and names* the narrow Shioaji surface that the execution
host (`runtime.TradingEngine` + its mixins) actually depends on via ``self.api``.
It is the formalization of an interface that already exists implicitly:

- Live:     ``TradingEngine(api=shioaji.Shioaji(...))``
- Backtest: ``TradingEngine(api=backtest.mock_broker.MockBroker(...))``
- Tests:    ``TradingEngine(api=MagicMock())`` (see ``tests.test_helpers.make_host``)

Because backtest already injects ``MockBroker`` as ``api`` and never calls the live
``start()`` path, the engine is *already* broker-agnostic. This file makes that
contract explicit so new broker adapters (or a future ``ShioajiBroker`` wrapper) have
a single reference for "what the engine needs".

Order *construction* lives in ``adapters`` (``ShioajiOrderAdapter`` / ``MockOrderAdapter``);
``runtime.order_executor`` calls ``self._order_adapter.place_ioc_limit(...)``.
Order event types use string constants in ``core.order_events`` (``FUTURES_ORDER`` /
``FUTURES_DEAL``), shared by live and mock paths.

This Protocol is used for typing/documentation only. It is NOT enforced at runtime,
so duck-typed stand-ins (``MockBroker``, ``MagicMock``) remain valid without
inheriting from it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

# Semantic label for tick quote subscription. Shioaji live adapters pass
# ``shioaji.constant.QuoteType.Tick`` (or ``sj.QuoteType.Tick``) as ``quote_type``
# to ``subscribe()``; the engine never references broker quote enums directly.
QUOTE_TYPE_TICK = "tick"

# ``list_positions`` return items should expose (duck-typed):
#   - code: str
#   - quantity: int
#   - direction: str or broker enum (normalize via adapters.position_normalizer)
#   - price: float (average entry / position price)


class BrokerPort(Protocol):
    """Narrow broker surface consumed by TradingEngine and its mixins.

    Signatures are kept loose (``Any``) on purpose: the goal is to name the seam,
    not to re-specify Shioaji's full typing. See the concrete implementations in
    ``backtest.mock_broker.MockBroker`` (replay) and ``shioaji.Shioaji`` (live).
    """

    # --- Account / contracts -------------------------------------------------
    futopt_account: Any
    Contracts: Any

    # --- Session lifecycle ---------------------------------------------------
    def login(self, *args: Any, **kwargs: Any) -> Any: ...
    def logout(self, *args: Any, **kwargs: Any) -> Any: ...
    def activate_ca(self, *args: Any, **kwargs: Any) -> Any: ...
    def subscribe_trade(self, *args: Any, **kwargs: Any) -> Any: ...
    def usage(self, *args: Any, **kwargs: Any) -> Any: ...

    # --- Market data ---------------------------------------------------------
    def kbars(self, *, contract: Any, start: str, end: str) -> Any: ...
    def subscribe(self, contract: Any, quote_type: Any = ...) -> Any: ...
    def on_tick_fop_v1(self, *args: Any, **kwargs: Any) -> Callable[[Callable], Callable]: ...

    # --- Callbacks (live) ----------------------------------------------------
    def set_order_callback(self, cb: Callable[..., Any]) -> Any: ...
    def set_event_callback(self, cb: Callable[..., Any]) -> Any: ...

    # --- Orders / positions --------------------------------------------------
    def place_order(self, contract: Any, order: Any, timeout: int = ...) -> Any: ...
    def update_status(self, *args: Any, **kwargs: Any) -> Any: ...
    def order_deal_records(self, *args: Any, **kwargs: Any) -> Any: ...
    def list_positions(self, *args: Any, **kwargs: Any) -> Any: ...


__all__ = ["BrokerPort", "QUOTE_TYPE_TICK"]
