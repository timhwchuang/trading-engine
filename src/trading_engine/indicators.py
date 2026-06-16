"""VWAP / momentum / ATR indicator state."""

from __future__ import annotations

import datetime
from collections import deque
from typing import Deque, Tuple

from trading_engine.core.types import MarketSnapshot


class IndicatorState:
    def __init__(
        self,
        *,
        vwap_window_min: int = 5,
        atr_period: int = 20,
    ) -> None:
        self._vwap_window_min = vwap_window_min
        self._atr_period = atr_period
        self.vwap_window: Deque[Tuple[int, float, int]] = deque()
        self.vwap_sum_pv = 0.0
        self.vwap_sum_vol = 0
        self.current_vwap = 0.0

        self.momentum_window: Deque[Tuple[int, int, int]] = deque()
        self.vol_1s = 0
        self.buy_vol_1s = 0
        self.sell_vol_1s = 0
        self.last_tick_price = 0.0

        self.current_atr = 0.0
        self.last_atr_refresh = 0.0
        self._atr_long_lookback_date: datetime.date | None = None
        self.trend_dir = "Flat"
        self.trend_strength = 0.0

    def update_vwap(self, ts: int, price: float, volume: int) -> None:
        self.vwap_window.append((ts, price, volume))
        self.vwap_sum_pv += price * volume
        self.vwap_sum_vol += volume

        cutoff = ts - self._vwap_window_min * 60
        while self.vwap_window and self.vwap_window[0][0] < cutoff:
            _old_ts, old_p, old_v = self.vwap_window.popleft()
            self.vwap_sum_pv -= old_p * old_v
            self.vwap_sum_vol -= old_v

        self.current_vwap = (
            self.vwap_sum_pv / self.vwap_sum_vol if self.vwap_sum_vol > 0 else price
        )

    def update_momentum(self, ts: int, volume: int, tick_type: int) -> None:
        self.momentum_window.append((ts, volume, tick_type))
        self.vol_1s += volume

        if tick_type == 1:
            self.buy_vol_1s += volume
        elif tick_type == 2:
            self.sell_vol_1s += volume

        cutoff = ts - 1
        while self.momentum_window and self.momentum_window[0][0] < cutoff:
            _old_ts, old_v, old_type = self.momentum_window.popleft()
            self.vol_1s -= old_v
            if old_type == 1:
                self.buy_vol_1s -= old_v
            elif old_type == 2:
                self.sell_vol_1s -= old_v

    def snapshot(
        self, ts: int, price: float, dt: datetime.datetime
    ) -> MarketSnapshot:
        return MarketSnapshot(
            ts=ts,
            price=price,
            dt=dt,
            vwap=self.current_vwap,
            vol_1s=self.vol_1s,
            buy_vol_1s=self.buy_vol_1s,
            sell_vol_1s=self.sell_vol_1s,
            current_atr=self.current_atr,
            trend_dir=self.trend_dir,
            trend_strength=self.trend_strength,
        )

    @classmethod
    def compute_atr(cls, kbars, *, atr_period: int | None = None) -> float:
        closes = kbars.Close
        highs = kbars.High
        lows = kbars.Low
        if len(closes) < 2:
            return 0.0

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        period_val = atr_period if atr_period is not None else 20
        period = min(period_val, len(trs))
        if period == 0:
            return 0.0
        return sum(trs[-period:]) / period
