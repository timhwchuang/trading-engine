"""Strategy interface (Protocol + optional ABC base).

The execution host (`runtime.TradingEngine`) and replay host (`backtest.BacktestEngine`)
inject a decision-logic instance via ``strategy=``. Implement ``Strategy`` (or subclass
``BaseStrategy``) and pass it to either host constructor.

Design goals:
- Code to interface, not implementation.
- Engine is the engine; strategy is the strategy.
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import Callable, Optional, Protocol

from trading_engine.core.audit.signal_audit import SignalAudit
from trading_engine.core.types import (
    MarketSnapshot,
    MomentumState,
    OrderSignal,
    PositionSnapshot,
    RiskGate,
    StrategySideEffects,
)


class Strategy(Protocol):
    """Pluggable strategy decision contract.

    The host is responsible for market snapshots, position/risk gates, vol thresholds,
    order execution, locks, and session lifecycle. The strategy owns signal generation
    and any intra-episode state (e.g. momentum tracking).
    """

    momentum: MomentumState

    def evaluate(
        self,
        market: MarketSnapshot,
        position: PositionSnapshot,
        risk: RiskGate,
        vol_threshold: tuple[float, float, float],
        *,
        session_force_flatten_time: datetime.time,
        max_daily_loss_points: float,
        on_daily_loss_block: Callable[[], None] | None = None,
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        """Core decision point. Returns (signal_or_None, side_effects)."""
        ...

    def reset(self) -> None:
        """Reset episode / momentum state (called by host after fills)."""
        ...

    def activate_momentum(self, direction: str, price: float, ts: int) -> None:
        ...

    def update_momentum_peak(self, price: float) -> None:
        ...

    def manage_exit(
        self, market: MarketSnapshot, position: PositionSnapshot
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        ...

    def build_entry_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        multiplier: float,
        vol_threshold: float,
    ) -> SignalAudit:
        ...

    def build_exit_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        reason: str,
        *,
        trail_points_used: float = 0.0,
    ) -> SignalAudit:
        ...

    def session_force_flatten_signal(
        self,
        market: MarketSnapshot,
        position: PositionSnapshot,
        session_force_flatten_time: datetime.time,
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        ...


class BaseStrategy(ABC):
    """Convenience ABC with default no-op / empty implementations."""

    def __init__(self) -> None:
        self.momentum = MomentumState(
            active=False,
            direction="None",
            peak=0.0,
            trigger_time=0,
        )

    @abstractmethod
    def evaluate(
        self,
        market: MarketSnapshot,
        position: PositionSnapshot,
        risk: RiskGate,
        vol_threshold: tuple[float, float, float],
        *,
        session_force_flatten_time: datetime.time,
        max_daily_loss_points: float,
        on_daily_loss_block: Callable[[], None] | None = None,
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        ...

    def reset(self) -> None:
        self.momentum = MomentumState(
            active=False,
            direction="None",
            peak=0.0,
            trigger_time=0,
        )

    def reset_momentum(self) -> None:
        """Backward-compatible alias; host calls ``reset()``."""
        self.reset()

    def activate_momentum(self, direction: str, price: float, ts: int) -> None:
        self.momentum = MomentumState(
            active=True,
            direction=direction,
            peak=price,
            trigger_time=ts,
        )

    def update_momentum_peak(self, price: float) -> None:
        if self.momentum.direction == "Long":
            self.momentum.peak = max(self.momentum.peak, price)
        elif self.momentum.direction == "Short":
            self.momentum.peak = min(self.momentum.peak, price)

    def manage_exit(
        self, market: MarketSnapshot, position: PositionSnapshot
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        return None, StrategySideEffects()

    def build_entry_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        multiplier: float,
        vol_threshold: float,
    ) -> SignalAudit:
        return SignalAudit(
            intent="entry",
            direction=direction,
            price=market.price,
            ts=market.ts,
            multiplier=multiplier,
            vol_threshold=vol_threshold,
        )

    def build_exit_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        reason: str,
        *,
        trail_points_used: float = 0.0,
    ) -> SignalAudit:
        return SignalAudit(
            intent="exit",
            direction=direction,
            price=market.price,
            ts=market.ts,
            reason=reason,
            trail_points_used=trail_points_used,
        )

    def session_force_flatten_signal(
        self,
        market: MarketSnapshot,
        position: PositionSnapshot,
        session_force_flatten_time: datetime.time,
    ) -> tuple[Optional[OrderSignal], StrategySideEffects]:
        return None, StrategySideEffects()


__all__ = ["Strategy", "StrategySideEffects", "BaseStrategy"]
