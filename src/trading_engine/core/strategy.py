"""Strategy interface (Protocol + optional ABC base).

The execution host (``TradingEngine``) and replay host (``BacktestEngine``)
inject a decision-logic instance via ``strategy=``. Implement ``Strategy`` (or
subclass ``BaseStrategy``) and pass it to either host constructor.

Design goals:
- Code to interface, not implementation.
- Engine is the engine; strategy is the strategy.
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Protocol

from trading_engine.core.audit.signal_audit import SignalAudit
from trading_engine.core.types import (
    MarketSnapshot,
    OrderSignal,
    PositionSnapshot,
    RiskGate,
    StrategySideEffects,
)


class Strategy(Protocol):
    """Pluggable strategy decision contract (community v1).

    Required: ``evaluate``, ``reset``.
    Optional helpers have no-op defaults on ``BaseStrategy``.
    """

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
    ) -> tuple[OrderSignal | None, StrategySideEffects]:
        """Core decision point. Returns (signal_or_None, side_effects)."""
        ...

    def reset(self) -> None:
        """Reset intra-episode state (called by host after fills / session)."""
        ...

    def manage_exit(
        self, market: MarketSnapshot, position: PositionSnapshot
    ) -> tuple[OrderSignal | None, StrategySideEffects]: ...

    def build_entry_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        multiplier: float,
        vol_threshold: float,
    ) -> SignalAudit: ...

    def build_exit_audit(
        self,
        market: MarketSnapshot,
        direction: str,
        reason: str,
        *,
        trail_points_used: float = 0.0,
    ) -> SignalAudit: ...

    def session_force_flatten_signal(
        self,
        market: MarketSnapshot,
        position: PositionSnapshot,
        session_force_flatten_time: datetime.time,
    ) -> tuple[OrderSignal | None, StrategySideEffects]: ...


class BaseStrategy(ABC):
    """Convenience ABC with default no-op / empty implementations."""

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
    ) -> tuple[OrderSignal | None, StrategySideEffects]: ...

    def reset(self) -> None:
        """Reset strategy-local state. Override in plugins as needed."""
        return None

    def manage_exit(
        self, market: MarketSnapshot, position: PositionSnapshot
    ) -> tuple[OrderSignal | None, StrategySideEffects]:
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
    ) -> tuple[OrderSignal | None, StrategySideEffects]:
        return None, StrategySideEffects()


__all__ = ["Strategy", "StrategySideEffects", "BaseStrategy"]
