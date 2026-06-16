"""Default Settings matching reference config.yaml (for unit tests)."""

from __future__ import annotations

import datetime
from pathlib import Path

from trading_engine.core.runtime_config import RuntimeConfig
from trading_engine.settings import Settings


def default_test_settings() -> Settings:
    return Settings(
        simulation=True,
        product_code="TXFR1",
        vwap_window_min=5,
        entry_band_points=2.0,
        momentum_vol_1s=150,
        momentum_buy_ratio=0.80,
        momentum_sell_ratio=0.78,
        exhaustion_vol=15,
        cooldown_sec=10,
        momentum_timeout_sec=180,
        max_daily_loss_points=120,
        max_consecutive_loss=4,
        fixed_tp_points=20,
        trail_points=8,
        atr_period=20,
        min_atr_threshold=25.0,
        atr_refresh_sec=300,
        atr_kline_lookback_days=10,
        pending_timeout_sec=8,
        ioc_slippage_points=3,
        exit_grace_ticks=60,
        exit_grace_sec=30,
        hard_stop_points=6,
        vwap_stop_points=3,
        no_tick_timeout_sec=45,
        clock_skew_warn_sec=1.0,
        trend_filter_enabled=False,
        trend_timeframe_min=5,
        trend_mode="ema",
        trend_ema_period=20,
        trend_slope_min=0.0,
        trend_min_strength=0.0,
        trail_atr_k=0.25,
        trail_points_floor=8.0,
        vwap_stop_atr_k=0.25,
        vwap_stop_points_floor=3.0,
        atr_trailing_enabled=False,
        atr_vwap_stop_enabled=False,
        session_start=datetime.time(8, 45),
        session_end=datetime.time(13, 45),
        session_flatten_time=datetime.time(13, 40),
        session_force_flatten_time=datetime.time(13, 44),
        flatten_slippage_points=8,
        base_vol=150,
        atr_vol_mult=1.0,
        open_mult_futures=2.5,
        open_mult_spot=1.5,
        open_mult_normal=1.0,
        log_level="INFO",
        log_file="",
        exit_order_max_retries=3,
        exit_order_retry_delay_sec=1.0,
        session_watchdog_sec=30.0,
        session_relogin_max_attempts=5,
        session_relogin_backoff_base_sec=5.0,
        config_path=Path("config/config.yaml"),
    )


def default_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(default_test_settings())


__all__ = ["default_runtime_config", "default_test_settings"]
