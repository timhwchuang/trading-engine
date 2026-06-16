"""Settings dataclass — host app loads YAML/env and passes to RuntimeConfig."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    simulation: bool
    product_code: str

    vwap_window_min: int
    entry_band_points: float
    momentum_vol_1s: int
    momentum_buy_ratio: float
    momentum_sell_ratio: float
    exhaustion_vol: int
    cooldown_sec: int
    max_daily_loss_points: int
    max_consecutive_loss: int
    fixed_tp_points: int
    trail_points: int
    atr_period: int
    min_atr_threshold: float
    atr_refresh_sec: int
    atr_kline_lookback_days: int
    pending_timeout_sec: int
    ioc_slippage_points: int
    exit_grace_ticks: int
    exit_grace_sec: int
    hard_stop_points: int
    vwap_stop_points: int
    no_tick_timeout_sec: int
    clock_skew_warn_sec: float

    trend_filter_enabled: bool
    trend_timeframe_min: int
    trend_mode: str
    trend_ema_period: int
    trend_slope_min: float
    trend_min_strength: float
    trail_atr_k: float
    trail_points_floor: float
    vwap_stop_atr_k: float
    vwap_stop_points_floor: float
    atr_trailing_enabled: bool
    atr_vwap_stop_enabled: bool

    session_start: datetime.time
    session_end: datetime.time
    session_flatten_time: datetime.time
    session_force_flatten_time: datetime.time
    flatten_slippage_points: int

    base_vol: int
    atr_vol_mult: float
    open_mult_futures: float
    open_mult_spot: float
    open_mult_normal: float

    log_level: str
    log_file: str

    exit_order_max_retries: int
    exit_order_retry_delay_sec: float
    session_watchdog_sec: float
    session_relogin_max_attempts: int
    session_relogin_backoff_base_sec: float

    config_path: Path = Path("")


__all__ = ["Settings"]