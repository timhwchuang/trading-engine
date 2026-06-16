"""Market calendar port — exchange session/time helpers injected into TradingEngine."""

from __future__ import annotations

import datetime
from typing import Any, Protocol

import trading_engine.calendar.taifex as taifex


class MarketCalendarPort(Protocol):
    def trading_day_for_daily_reset(self, dt: datetime.datetime) -> datetime.date: ...

    def is_trading_session(
        self,
        dt: datetime.datetime,
        session_start: datetime.time,
        session_end: datetime.time,
    ) -> bool: ...

    def is_at_or_after(self, dt: datetime.datetime, cutoff: datetime.time) -> bool: ...

    def is_opening_session_window(self, dt: datetime.datetime) -> bool: ...

    def compute_vol_threshold(
        self,
        current_atr: float,
        dt: datetime.datetime,
        *,
        base_vol: float,
        atr_vol_mult: float,
        mult_futures: float,
        mult_spot: float,
        mult_normal: float,
    ) -> tuple[float, float, float]: ...

    def select_recent_trading_days_closes(
        self,
        raw_kbars: Any,
        reference_dt: datetime.datetime,
        *,
        max_days: int = 2,
    ) -> list[float]: ...


class TaifexMarketCalendar:
    """Default TAIFEX day-session calendar (Taiwan local time)."""

    def trading_day_for_daily_reset(self, dt: datetime.datetime) -> datetime.date:
        return taifex.trading_day_for_daily_reset(dt)

    def is_trading_session(
        self,
        dt: datetime.datetime,
        session_start: datetime.time,
        session_end: datetime.time,
    ) -> bool:
        return taifex.is_trading_session(dt, session_start, session_end)

    def is_at_or_after(self, dt: datetime.datetime, cutoff: datetime.time) -> bool:
        return taifex.is_at_or_after(dt, cutoff)

    def is_opening_session_window(self, dt: datetime.datetime) -> bool:
        return taifex.is_opening_session_window(dt)

    def compute_vol_threshold(
        self,
        current_atr: float,
        dt: datetime.datetime,
        *,
        base_vol: float,
        atr_vol_mult: float,
        mult_futures: float,
        mult_spot: float,
        mult_normal: float,
    ) -> tuple[float, float, float]:
        return taifex.compute_vol_threshold(
            current_atr,
            dt,
            base_vol=base_vol,
            atr_vol_mult=atr_vol_mult,
            mult_futures=mult_futures,
            mult_spot=mult_spot,
            mult_normal=mult_normal,
        )

    def select_recent_trading_days_closes(
        self,
        raw_kbars: Any,
        reference_dt: datetime.datetime,
        *,
        max_days: int = 2,
    ) -> list[float]:
        return taifex.select_recent_trading_days_closes(raw_kbars, reference_dt, max_days=max_days)


__all__ = ["MarketCalendarPort", "TaifexMarketCalendar"]
