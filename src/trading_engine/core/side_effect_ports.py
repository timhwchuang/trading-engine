"""Injectable side-effect ports: alerts, archive, trend refresh, telemetry."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Protocol

from trading_engine.core.runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)


class AlertPort(Protocol):
    def send(self, message: str, *, level: str = "WARNING") -> bool: ...


class NullAlertPort:
    def send(self, message: str, *, level: str = "WARNING") -> bool:
        logger.info("ALERT [%s] %s", level, message)
        return False


class ArchivePort(Protocol):
    def maybe_start_tick_archive(self, product_code: str) -> Any: ...

    def enqueue_tick(self, tick: Any, tick_type: int) -> None: ...

    def shutdown_tick_archive(self) -> None: ...

    def archive_kbars(
        self, kbars: Any, *, product_code: str, trade_date: datetime.date
    ) -> None: ...


class NullArchivePort:
    def maybe_start_tick_archive(self, product_code: str) -> Any:
        return None

    def enqueue_tick(self, tick: Any, tick_type: int) -> None:
        return None

    def shutdown_tick_archive(self) -> None:
        return None

    def archive_kbars(self, kbars: Any, *, product_code: str, trade_date: datetime.date) -> None:
        return None


class TrendRefreshPort(Protocol):
    def refresh_trend(
        self,
        kbars: Any,
        *,
        exchange_dt: datetime.datetime | None,
        used_long_lookback: bool,
        atr: float,
        cfg: RuntimeConfig,
    ) -> tuple[str, float]: ...


class NullTrendRefreshPort:
    def refresh_trend(
        self,
        kbars: Any,
        *,
        exchange_dt: datetime.datetime | None,
        used_long_lookback: bool,
        atr: float,
        cfg: RuntimeConfig,
    ) -> tuple[str, float]:
        return "Flat", 0.0


class NullTelemetryPort:
    """Minimal telemetry for tests / backtest without app-layer observability."""

    def record_lock_wait(self, ms: float) -> None:
        return None

    def record_atr(self, atr: float) -> None:
        return None

    def record_entry_signal(self) -> None:
        return None

    def record_exit_signal(self) -> None:
        return None

    def record_tick_type(self, original: int, effective: int) -> None:
        return None

    def record_intent_cancelled(self, tag: str) -> None:
        return None

    def record_no_tick_resubscribe(self) -> None:
        return None

    def reset(self) -> None:
        return None

    def snapshot_tick_types(self, counts: Any) -> None:
        return None

    def update_risk_state(self, daily_pnl: float, consecutive_loss: int) -> None:
        return None

    def record_fill(self, **kwargs: Any) -> Any:
        return kwargs

    def build_summary(self, trade_date: str) -> dict[str, Any]:
        return {"date": trade_date}

    def format_daily_summary(self, summary: dict[str, Any]) -> str:
        import json

        return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))

    def format_fill_audit(self, audit: Any) -> str:
        import json

        if hasattr(audit, "__dataclass_fields__"):
            from dataclasses import asdict

            return json.dumps(asdict(audit), ensure_ascii=False, separators=(",", ":"))
        return json.dumps(audit, ensure_ascii=False, separators=(",", ":"))

    def compute_limit_price(self, signal_price: float, *, is_buy: bool, ioc_slippage: int) -> float:
        if is_buy:
            return signal_price + ioc_slippage
        return signal_price - ioc_slippage


class TelemetryPort(Protocol):
    def record_lock_wait(self, ms: float) -> None: ...

    def record_atr(self, atr: float) -> None: ...

    def record_entry_signal(self) -> None: ...

    def record_exit_signal(self) -> None: ...

    def record_tick_type(self, original: int, effective: int) -> None: ...

    def record_intent_cancelled(self, tag: str) -> None: ...

    def record_no_tick_resubscribe(self) -> None: ...

    def reset(self) -> None: ...

    def snapshot_tick_types(self, counts: Any) -> None: ...

    def update_risk_state(self, daily_pnl: float, consecutive_loss: int) -> None: ...

    def record_fill(self, **kwargs: Any) -> Any: ...

    def build_summary(self, trade_date: str) -> dict[str, Any]: ...

    def format_daily_summary(self, summary: dict[str, Any]) -> str: ...

    def format_fill_audit(self, audit: Any) -> str: ...

    def compute_limit_price(
        self, signal_price: float, *, is_buy: bool, ioc_slippage: int
    ) -> float: ...


__all__ = [
    "AlertPort",
    "ArchivePort",
    "NullAlertPort",
    "NullArchivePort",
    "NullTelemetryPort",
    "NullTrendRefreshPort",
    "TelemetryPort",
    "TrendRefreshPort",
]
