"""TradingEngine test factory (no app-layer wiring)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from trading_engine.adapters.mock import MockOrderAdapter
from trading_engine.core.side_effect_ports import (
    NullAlertPort,
    NullArchivePort,
    NullTelemetryPort,
    NullTrendRefreshPort,
)
from trading_engine.core.strategy import BaseStrategy, Strategy, StrategySideEffects
from trading_engine.engine import TradingEngine
from trading_engine.testing.defaults import default_runtime_config


class StubStrategy(BaseStrategy):
    """No-op strategy for kernel tests."""

    def evaluate(self, *args, **kwargs):
        return None, StrategySideEffects()

    def reset(self) -> None:
        return None


def make_host(
    decision: Strategy | None = None,
    *,
    api: Any | None = None,
) -> TradingEngine:
    broker = api if api is not None else MagicMock()
    cfg = default_runtime_config()
    strategy = decision if decision is not None else StubStrategy()
    return TradingEngine(
        api=broker,
        strategy=strategy,
        runtime_config=cfg,
        order_adapter=MockOrderAdapter(broker),
        telemetry=NullTelemetryPort(),
        trend_refresh=NullTrendRefreshPort(),
        alerts=NullAlertPort(),
        archive=NullArchivePort(),
    )


def arm_pending_entry(
    host: TradingEngine,
    *,
    order_id: str = "ord-entry-1",
    signal_price: float = 18000.0,
    exchange_ts: int = 1000,
    qty: int = 1,
) -> None:
    """Arm a pending entry for kernel tests. Phase 1: supports qty."""
    host.is_pending = True
    host.pending_intent = "entry"
    host.pending_order_id = order_id
    host.pending_qty = qty
    host.pending_exchange_ts = exchange_ts
    host.pending_signal_price = signal_price
    host.pending_limit_price = signal_price + 3
    host.pending_ioc_slippage = 3


def arm_pending_exit(
    host: TradingEngine,
    *,
    order_id: str = "ord-exit-1",
    signal_price: float = 18020.0,
    exchange_ts: int = 2000,
    exit_reason: str = "take_profit",
    qty: int = 1,
) -> None:
    """Arm a pending exit for kernel tests. Phase 1: supports qty (for reconstruct)."""
    host.is_pending = True
    host.pending_intent = "exit"
    host.pending_order_id = order_id
    host.pending_qty = qty
    host.pending_exchange_ts = exchange_ts
    host.pending_signal_price = signal_price
    host.pending_limit_price = signal_price - 3
    host.pending_ioc_slippage = 3
    host.pending_exit_reason = exit_reason


def make_broker_with_positions(*positions: dict) -> MagicMock:
    """Create a MagicMock broker whose list_positions returns the given position dicts.

    Each position dict should have keys: code, quantity, direction, price (mimics shioaji position).
    Useful for sync_positions adversarial tests.
    """
    broker = MagicMock()
    pos_objects = []
    for p in positions:
        pos = MagicMock()
        pos.code = p.get("code", "TXFR1")
        pos.quantity = int(p.get("quantity", 0))
        pos.direction = p.get("direction", "Buy")
        pos.price = float(p.get("price", 18000.0))
        pos_objects.append(pos)
    broker.list_positions.return_value = pos_objects
    broker.futopt_account = MagicMock()
    return broker


__all__ = ["StubStrategy", "arm_pending_entry", "arm_pending_exit", "make_host", "make_broker_with_positions"]
