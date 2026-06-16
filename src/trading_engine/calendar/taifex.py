"""Exchange-time helpers (Taiwan / TAIFEX).

策略內所有「幾點幾分」與 tick 驅動的時間差一律用 tick.datetime（交易所時間）。
"""

from __future__ import annotations

import datetime
from collections import OrderedDict
from typing import Any

TAIWAN_TZ = datetime.timezone(datetime.timedelta(hours=8))


def exchange_local_dt(dt: datetime.datetime) -> datetime.datetime:
    """Normalize tick datetime to Taiwan local (naive = already exchange local)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(TAIWAN_TZ)


def exchange_local_time(dt: datetime.datetime) -> datetime.time:
    return exchange_local_dt(dt).time()


def exchange_date(dt: datetime.datetime) -> datetime.date:
    return exchange_local_dt(dt).date()


def trading_day_for_daily_reset(dt: datetime.datetime) -> datetime.date:
    """P0-8: 日內風控重置用的「交易日」。

    目前策略僅日盤（08:45–13:45），交易日 = 台灣日曆日。
    若未來擴展夜盤，須改為 TAIFEX 交易日（切換點約 15:00），不可再用午夜日曆日。
    """
    return exchange_date(dt)


def is_trading_session(
    dt: datetime.datetime,
    session_start: datetime.time,
    session_end: datetime.time,
) -> bool:
    """SESSION_START <= t <= SESSION_END (inclusive on both ends)."""
    t = exchange_local_time(dt)
    return session_start <= t <= session_end


# P1-2 opening windows (exchange local, half-open intervals)
_OPEN_FUTURES = datetime.time(8, 45)
_OPEN_SPOT = datetime.time(9, 0)
_OPEN_NORMAL = datetime.time(9, 15)


def opening_session_multiplier(
    dt: datetime.datetime,
    *,
    mult_futures: float,
    mult_spot: float,
    mult_normal: float,
) -> float:
    """08:45 <= t < 09:00 → futures; 09:00 <= t < 09:15 → spot; else normal."""
    t = exchange_local_time(dt)
    if _OPEN_FUTURES <= t < _OPEN_SPOT:
        return mult_futures
    if _OPEN_SPOT <= t < _OPEN_NORMAL:
        return mult_spot
    return mult_normal


def is_at_or_after(dt: datetime.datetime, cutoff: datetime.time) -> bool:
    """True when exchange local time >= cutoff (inclusive)."""
    return exchange_local_time(dt) >= cutoff


def is_opening_session_window(dt: datetime.datetime) -> bool:
    """08:45 <= t < 09:15（期貨 + 現貨開盤衝擊窗）；P2-5 IOC 取消統計用。"""
    t = exchange_local_time(dt)
    return _OPEN_FUTURES <= t < _OPEN_NORMAL


def compute_vol_threshold(
    current_atr: float,
    dt: datetime.datetime,
    *,
    base_vol: float,
    atr_vol_mult: float,
    mult_futures: float,
    mult_spot: float,
    mult_normal: float,
) -> tuple[float, float, float]:
    """Return (base_vol, multiplier, vol_threshold)."""
    effective_base = max(base_vol, current_atr * atr_vol_mult)
    multiplier = opening_session_multiplier(
        dt,
        mult_futures=mult_futures,
        mult_spot=mult_spot,
        mult_normal=mult_normal,
    )
    return effective_base, multiplier, effective_base * multiplier


def _ts_ns_to_naive_dt(ts_ns: int) -> datetime.datetime:
    """Shioaji kbars/ts ns epoch -> naive Taipei local (matches tick.datetime + KBarRecord.ts)."""
    aware = datetime.datetime.fromtimestamp(ts_ns / 1_000_000_000, TAIWAN_TZ)
    return aware.replace(tzinfo=None)


def select_recent_trading_days_closes(
    raw_kbars: Any,
    reference_dt: datetime.datetime,
    *,
    max_days: int = 2,
) -> list[float]:
    """P6-1-CAL-1: Return 1m closes belonging to the most recent N trading days in the kbars data.

    Uses kbar Datetime (via ts) + trading_day_for_daily_reset to cut cross-session / night / gap pollution
    that the old approx_bars_per_trading_day=400 heuristic could suffer.

    IMPORTANT SCOPE (honest calibration note per CQR hygiene):
    - Effective regime detection scale and strength threshold power remain *exclusively* determined by
      resample_closes(timeframe_min) + ema_period/slope_min + min_strength (ATR-normalized) inside compute_trend.
      This helper *only* solves cross-trading-day / night / gap bar inclusion into the *input list* fed to compute_trend.
    - All unit coverage and regression guards use synthetic data. Real UAT tick + KBARS_ARCHIVE calibration
      (B-class P6-1-CAL-6/7) is still required before trusting impact on live trend_dir/strength, veto_rate, or
      delta expectancy numbers. Do not treat synthetic guard as statistical edge proof.
    - Default max_days=2 is chosen to guarantee the HTF detector has enough recent bars to fill ema_period
      windows even when "today" (at first used_long ATR pull / open) has very few 1m bars so far; it trades off
      vs. including exactly one prior full trading day's closes. Rationale is engineering (HTF window fill) not
      a claim of "macro bias".

    Accepts:
    - Shioaji-style raw (has .ts list[int ns] parallel to .Close)
    - Iterable of objects with .ts (datetime) and .Close (e.g. KBarRecord list)

    Keeps chronological order. "Recent" is by distinct trading_day_for_daily_reset values present,
    taking the last up to max_days (today's partial bars are included if their trading day matches).
    This replaces the TXF-magic length slice while still giving the HTF detector ~1-2 days of HTF bars.
    """
    # Normalize to parallel lists of (dt, close)
    pairs: list[tuple[datetime.datetime, float]] = []
    ts_list = list(getattr(raw_kbars, "ts", []) or [])
    close_list = list(getattr(raw_kbars, "Close", []) or [])
    if ts_list and close_list and len(ts_list) == len(close_list):
        for i in range(len(ts_list)):
            try:
                dt = _ts_ns_to_naive_dt(int(ts_list[i]))
            except (TypeError, ValueError, OverflowError, OSError):
                # Fallback only on parse failure (rare); reference_dt anchors the day for this bar
                # (see engine call site: passes _last_tick_exchange_dt or now()).
                dt = ts_list[i] if isinstance(ts_list[i], datetime.datetime) else reference_dt
            pairs.append((dt, float(close_list[i])))
    else:
        # Assume sequence of records with .ts (dt) + .Close
        for rec in raw_kbars or []:
            ts = getattr(rec, "ts", None)
            if ts is None:
                continue
            dt = ts if isinstance(ts, datetime.datetime) else reference_dt
            c = getattr(rec, "Close", None)
            if c is not None:
                pairs.append((dt, float(c)))

    if not pairs:
        return []

    # Group by trading day (session-aware)
    day_to_closes: OrderedDict[datetime.date, list[float]] = OrderedDict()
    for dt, c in pairs:
        day = trading_day_for_daily_reset(dt)
        day_to_closes.setdefault(day, []).append(c)

    # Most recent days present (by appearance order in data, which is chrono; take tail)
    days = list(day_to_closes.keys())
    selected_days = set(days[-max_days:]) if days else set()

    # Reconstruct in original bar order, only selected days
    out: list[float] = []
    for dt, c in pairs:
        if trading_day_for_daily_reset(dt) in selected_days:
            out.append(c)
    return out


__all__ = [
    "TAIWAN_TZ",
    "compute_vol_threshold",
    "exchange_date",
    "exchange_local_dt",
    "exchange_local_time",
    "is_at_or_after",
    "is_opening_session_window",
    "is_trading_session",
    "opening_session_multiplier",
    "select_recent_trading_days_closes",
    "trading_day_for_daily_reset",
]