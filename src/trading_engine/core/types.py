"""Shared runtime types used across strategy, runtime, and backtest."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from trading_engine.core.audit.signal_audit import SignalAudit


@dataclass
class OrderSignal:
    action: str  # "Buy" | "Sell"
    qty: int
    ref_price: float
    intent: str  # "entry" | "exit"
    exchange_ts: int = 0
    audit: Optional[SignalAudit] = None
    slippage_points: Optional[int] = None


@dataclass
class MarketSnapshot:
    """Indicator + market state at a single tick."""

    ts: int
    price: float
    dt: datetime.datetime
    vwap: float
    vol_1s: int
    buy_vol_1s: int
    sell_vol_1s: int
    current_atr: float
    trend_dir: str
    trend_strength: float


@dataclass
class PositionSnapshot:
    has_position: bool
    position_dir: str
    entry_price: float
    trailing_peak: float
    entry_exchange_ts: int
    ticks_since_entry: int
    qty: int = 0


@dataclass
class MomentumState:
    active: bool
    direction: str
    peak: float
    trigger_time: int


@dataclass
class RiskGate:
    """Pre-computed runtime guards passed into strategy evaluation."""

    api_connected: bool
    is_pending: bool
    exit_pending: bool
    cooldown_active: bool
    in_trading_session: bool
    block_new_entry: bool
    consecutive_loss: int
    daily_pnl: float
    after_flatten_time: bool
    force_flatten: bool


@dataclass
class StrategySideEffects:
    """Side effects returned by a Strategy's evaluate() method.

    Currently only used for the daily loss block, but kept extensible.
    """

    block_new_entry: bool = False


@dataclass
class TickSnapshot:
    """Broker-agnostic normalized tick used internally by the engine.

    Live adapters (e.g. Shioaji) are responsible for converting their native
    tick objects into this before calling into engine hot paths.
    """

    ts: int
    price: float
    volume: int
    tick_type: int
    exchange_dt: datetime.datetime
