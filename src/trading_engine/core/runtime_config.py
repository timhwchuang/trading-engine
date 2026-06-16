"""Runtime configuration injected into TradingEngine."""

from __future__ import annotations

import os
from typing import Any

from trading_engine.settings import Settings

RuntimeConfigBase = Settings
_MISSING = object()

SWEEP_FIELD_TO_CONST: dict[str, str] = {
    "entry_band_points": "ENTRY_BAND_POINTS",
    "vwap_stop_points": "VWAP_STOP_POINTS",
    "exhaustion_vol": "EXHAUSTION_VOL",
    "exit_grace_ticks": "EXIT_GRACE_TICKS",
    "fixed_tp_points": "FIXED_TP_POINTS",
    "trail_points": "TRAIL_POINTS",
    "hard_stop_points": "HARD_STOP_POINTS",
    "trend_filter_enabled": "TREND_FILTER_ENABLED",
    "trend_min_strength": "TREND_MIN_STRENGTH",
    "trend_timeframe_min": "TREND_TIMEFRAME_MIN",
    "trend_mode": "TREND_MODE",
    "trend_ema_period": "TREND_EMA_PERIOD",
    "trend_slope_min": "TREND_SLOPE_MIN",
}

_CONST_TO_SNAKE = {
    "ENTRY_BAND_POINTS": "entry_band_points",
    "VWAP_STOP_POINTS": "vwap_stop_points",
    "EXHAUSTION_VOL": "exhaustion_vol",
    "EXIT_GRACE_TICKS": "exit_grace_ticks",
    "FIXED_TP_POINTS": "fixed_tp_points",
    "TRAIL_POINTS": "trail_points",
    "HARD_STOP_POINTS": "hard_stop_points",
    "TREND_FILTER_ENABLED": "trend_filter_enabled",
    "TREND_MIN_STRENGTH": "trend_min_strength",
    "TREND_TIMEFRAME_MIN": "trend_timeframe_min",
    "TREND_MODE": "trend_mode",
    "TREND_EMA_PERIOD": "trend_ema_period",
    "TREND_SLOPE_MIN": "trend_slope_min",
    "MOMENTUM_BUY_RATIO": "momentum_buy_ratio",
    "MOMENTUM_SELL_RATIO": "momentum_sell_ratio",
    "MIN_ATR_THRESHOLD": "min_atr_threshold",
    "MAX_CONSECUTIVE_LOSS": "max_consecutive_loss",
    "ATR_TRAILING_ENABLED": "atr_trailing_enabled",
    "ATR_VWAP_STOP_ENABLED": "atr_vwap_stop_enabled",
    "TRAIL_POINTS_FLOOR": "trail_points_floor",
    "TRAIL_ATR_K": "trail_atr_k",
    "VWAP_STOP_POINTS_FLOOR": "vwap_stop_points_floor",
    "VWAP_STOP_ATR_K": "vwap_stop_atr_k",
    "FLATTEN_SLIPPAGE_POINTS": "flatten_slippage_points",
    "EXIT_GRACE_SEC": "exit_grace_sec",
}


def normalize_overlay_key(key: str) -> str:
    return SWEEP_FIELD_TO_CONST.get(key, key)


def _snake_for_const(name: str) -> str:
    return _CONST_TO_SNAKE.get(name, name.lower())


class RuntimeConfig:
    """Frozen Settings + per-instance sweep overlay (no module-level patch)."""

    def __init__(
        self,
        base: Settings,
        overlay: dict[str, Any] | None = None,
    ) -> None:
        self._base = base
        self._overlay: dict[str, Any] = dict(overlay or {})

    def live_get(self, name: str, default: Any = None) -> Any:
        if name in self._overlay:
            return self._overlay[name]
        snake = _snake_for_const(name)
        if hasattr(self._base, snake):
            return getattr(self._base, snake)
        return default

    def apply_overlay(self, params: dict[str, Any]) -> dict[str, Any]:
        saved: dict[str, Any] = {}
        for key, value in params.items():
            real_key = normalize_overlay_key(key)
            saved[real_key] = self._overlay.get(real_key, _MISSING)
            self._overlay[real_key] = value
        return saved

    def restore_overlay(self, saved: dict[str, Any]) -> None:
        for key, old in saved.items():
            if old is _MISSING:
                self._overlay.pop(key, None)
            else:
                self._overlay[key] = old

    def config_snapshot_fields(self) -> dict[str, Any]:
        """Sweepable strategy fields for DAILY_SUMMARY embedding."""
        out: dict[str, Any] = {}
        for field, const in SWEEP_FIELD_TO_CONST.items():
            out[field] = self.live_get(const, getattr(self._base, field, None))
        return out

    @property
    def api_key(self) -> str:
        return os.environ.get("SJ_API_KEY", "YOUR_API_KEY")

    @property
    def secret_key(self) -> str:
        return os.environ.get("SJ_SEC_KEY", "YOUR_SECRET_KEY")

    @property
    def ca_path(self) -> str:
        return os.environ.get("SJ_CA_PATH", "")

    @property
    def ca_passwd(self) -> str:
        return os.environ.get("SJ_CA_PASSWD", "")

    @property
    def dump_order_events(self) -> bool:
        return False

    @property
    def tick_archive(self) -> bool:
        return False

    @property
    def kbars_archive(self) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


__all__ = [
    "RuntimeConfig",
    "RuntimeConfigBase",
    "SWEEP_FIELD_TO_CONST",
    "normalize_overlay_key",
]