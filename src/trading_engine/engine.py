from __future__ import annotations

import atexit
import os
import time
import datetime
import logging
import logging.handlers
import queue
import sys
from collections import deque
import threading
from typing import Any, Callable, Deque, List, Optional, Tuple

from trading_engine.core.ports import BrokerPort
from trading_engine.core.types import OrderSignal, TickSnapshot
from trading_engine.calendar.port import MarketCalendarPort, TaifexMarketCalendar
from trading_engine.core.audit.signal_audit import SignalAudit, format_signal_audit
from trading_engine.order_errors import (
    OrderErrorCategory,
    classify_order_error,
    should_retry_order,
)
from trading_engine.indicators import IndicatorState
from trading_engine.core.strategy import Strategy
from trading_engine.core.types import PositionSnapshot, RiskGate
from trading_engine.core.runtime_config import RuntimeConfig
from trading_engine.core.side_effect_ports import (
    AlertPort,
    ArchivePort,
    NullAlertPort,
    NullArchivePort,
    NullTelemetryPort,
    NullTrendRefreshPort,
    TelemetryPort,
    TrendRefreshPort,
)

from trading_engine.logging_setup import setup_async_logging, shutdown_async_logging

logger = setup_async_logging()

from trading_engine.order_executor import OrderExecutorMixin
from trading_engine.session import SessionMixin


class TradingEngine(OrderExecutorMixin, SessionMixin):
    def __init__(
        self,
        api: BrokerPort,
        clock: Any = None,
        strategy: Strategy | None = None,
        runtime_config: RuntimeConfig | None = None,
        order_adapter: Any = None,
        telemetry: TelemetryPort | None = None,
        alerts: AlertPort | None = None,
        archive: ArchivePort | None = None,
        trend_refresh: TrendRefreshPort | None = None,
        calendar: MarketCalendarPort | None = None,
    ):
        if runtime_config is None:
            raise TypeError("runtime_config is required; inject at app layer")
        if order_adapter is None:
            raise TypeError("order_adapter is required; inject at app layer")
        self._cfg = runtime_config
        self._telemetry = telemetry or NullTelemetryPort()
        self._alerts = alerts or NullAlertPort()
        self._archive = archive or NullArchivePort()
        self._trend_refresh = trend_refresh or NullTrendRefreshPort()
        self._calendar = calendar or TaifexMarketCalendar()
        if api is None:
            raise TypeError("api is required; inject a BrokerPort at the app layer")
        self.api = api
        self._order_adapter = order_adapter
        # Optional hook set by live bootstrap (e.g. ShioajiLiveBootstrap.subscribe_tick).
        self._resubscribe_ticks: Optional[Callable[[], None]] = None
        # 注入式時鐘：實盤預設 time.time()；回測傳入 tick 時間驅動的時鐘以確保確定性。
        self._clock = clock if clock is not None else time.time
        if strategy is None:
            raise TypeError("strategy is required; inject at app layer")

        # 持倉狀態（Phase 1: position_qty 為單一事實來源；has_position 為 derived property）
        self.position_qty = 0
        self.position_dir = "Flat"          # Long / Short / Flat
        self.entry_price = 0.0
        self.entry_exchange_ts = 0
        self.ticks_since_entry = 0
        self.trailing_peak = 0.0
        self.last_exit_time = 0
        self.daily_pnl = 0.0
        self.consecutive_loss = 0
        self.block_new_entry = False
        self._trading_date: Optional[datetime.date] = None

        # 下單狀態
        self.is_pending = False
        self.pending_intent: Optional[str] = None
        self.exit_pending = False
        self.pending_trade = None
        self.pending_order_id: Optional[str] = None
        self.pending_since = 0.0          # system time; relative pending timeout only
        self.pending_exchange_ts = 0
        self.pending_qty = 0
        self.pending_signal_price = 0.0
        self.pending_limit_price = 0.0
        self.pending_exit_reason = ""
        self.pending_ioc_slippage = self._cfg.ioc_slippage_points
        self.filled_qty = 0               # P2-1: 累計部分成交；IOC 結束前不全解鎖；多口管理前置（Mock+單測）
        self._resynced_position = False   # sync_positions 後待首 tick 校準 trailing_peak
        self._api_connected = True
        self._disconnect_since = 0.0
        self._session_relogin_attempts = 0
        self._next_relogin_at = 0.0
        self._exit_order_retry_count = 0
        self._exit_order_retry_at = 0.0
        self._pending_action: Optional[str] = None

        self.indicators = IndicatorState(
            vwap_window_min=self._cfg.vwap_window_min,
            atr_period=self._cfg.atr_period,
        )
        self.strategy: Strategy = strategy

        self.lock = threading.Lock()
        self.contract = None
        self._running = False
        self._raw_order_evt_dumped: set = set()
        self.last_tick_exchange_ts = 0
        self._last_tick_wall_time = 0.0
        self._last_tick_exchange_dt: Optional[datetime.datetime] = None
        self._tick_type_counts = {0: 0, 1: 0, 2: 0}
        self._tick_type_inferred_counts = {1: 0, 2: 0}
        self._last_tick_type_log_wall = 0.0
        self._last_clock_skew_warn_wall = 0.0
        self._last_no_tick_resubscribe_wall = 0.0
        self._pending_intent_cancel_exchange_dt: Optional[datetime.datetime] = None
        self._order_queue: queue.Queue[Optional[OrderSignal]] = queue.Queue()
        self._order_sync_mode = False
        self._order_worker_started = False

    @property
    def current_vwap(self) -> float:
        return self.indicators.current_vwap

    @current_vwap.setter
    def current_vwap(self, value: float) -> None:
        self.indicators.current_vwap = value

    @property
    def vol_1s(self) -> int:
        return self.indicators.vol_1s

    @vol_1s.setter
    def vol_1s(self, value: int) -> None:
        self.indicators.vol_1s = value

    @property
    def buy_vol_1s(self) -> int:
        return self.indicators.buy_vol_1s

    @property
    def sell_vol_1s(self) -> int:
        return self.indicators.sell_vol_1s

    @property
    def current_atr(self) -> float:
        return self.indicators.current_atr

    @current_atr.setter
    def current_atr(self, value: float) -> None:
        self.indicators.current_atr = value

    @property
    def last_atr_refresh(self) -> float:
        return self.indicators.last_atr_refresh

    @last_atr_refresh.setter
    def last_atr_refresh(self, value: float) -> None:
        self.indicators.last_atr_refresh = value

    @property
    def trend_dir(self) -> str:
        return self.indicators.trend_dir

    @trend_dir.setter
    def trend_dir(self, value: str) -> None:
        self.indicators.trend_dir = value

    @property
    def trend_strength(self) -> float:
        return self.indicators.trend_strength

    @property
    def has_position(self) -> bool:
        """Derived from position_qty (single source of truth for Phase 1+)."""
        return self.position_qty > 0

    def build_entry_audit(
        self, dt: datetime.datetime, price: float, ts: int, direction: str
    ) -> SignalAudit:
        vol_threshold = self._vol_threshold(dt)
        market = self.indicators.snapshot(ts, price, dt)
        base_vol, multiplier, threshold = vol_threshold
        return self.strategy.build_entry_audit(
            market, direction, multiplier, threshold
        )

    def build_exit_audit(
        self,
        price: float,
        ts: int,
        direction: str,
        reason: str,
        *,
        trail_points_used: float = 0.0,
    ) -> SignalAudit:
        dt = self._last_tick_exchange_dt or datetime.datetime.fromtimestamp(ts)
        market = self.indicators.snapshot(ts, price, dt)
        return self.strategy.build_exit_audit(
            market, direction, reason, trail_points_used=trail_points_used
        )

    def _position_snapshot(self) -> PositionSnapshot:
        return PositionSnapshot(
            has_position=self.has_position,
            position_dir=self.position_dir,
            entry_price=self.entry_price,
            trailing_peak=self.trailing_peak,
            entry_exchange_ts=self.entry_exchange_ts,
            ticks_since_entry=self.ticks_since_entry,
            qty=self.position_qty,
        )

    def _risk_gate(self, ts: int, dt: datetime.datetime) -> RiskGate:
        return RiskGate(
            api_connected=self._api_connected,
            is_pending=self.is_pending,
            exit_pending=self.exit_pending,
            cooldown_active=ts - self.last_exit_time < self._cfg.cooldown_sec,
            in_trading_session=self.is_trading_session(dt),
            block_new_entry=self.block_new_entry,
            consecutive_loss=self.consecutive_loss,
            daily_pnl=self.daily_pnl,
            after_flatten_time=self._calendar.is_at_or_after(
                dt, self._cfg.session_flatten_time
            ),
            force_flatten=self._calendar.is_at_or_after(
                dt, self._cfg.session_force_flatten_time
            ),
        )

    def _parse_tick_locked(
        self, tick: Any
    ) -> Tuple[int, float, int, int, int]:
        """Parse tick inside lock; infer buy/sell from price when type0."""
        ts = int(tick.datetime.timestamp())
        price = float(tick.close)
        volume = int(tick.volume)
        original_tick_type = int(getattr(tick, "tick_type", 0) or 0)
        tick_type = original_tick_type

        if tick_type == 0 and self.indicators.last_tick_price > 0:
            if price > self.indicators.last_tick_price:
                tick_type = 1
            elif price < self.indicators.last_tick_price:
                tick_type = 2

        self.indicators.last_tick_price = price
        if original_tick_type == 0 and tick_type in (1, 2):
            self._tick_type_inferred_counts[tick_type] = (
                self._tick_type_inferred_counts.get(tick_type, 0) + 1
            )
            self._telemetry.record_tick_type(original_tick_type, tick_type)
        return ts, price, volume, tick_type, original_tick_type

    def on_tick(self, tick: Any):
        """Accept either native broker tick (e.g. Shioaji TickFOPv1 via live adapter)
        or a TickSnapshot (preferred internal normalized form for decoupling).
        """
        signal: Optional[OrderSignal] = None
        ts = 0
        price = 0.0
        volume = 0
        tick_type = 0
        original_tick_type = 0
        exchange_dt = None
        lock_wait_start = time.perf_counter()
        with self.lock:
            self._telemetry.record_lock_wait((time.perf_counter() - lock_wait_start) * 1000)

            if isinstance(tick, TickSnapshot):
                ts = tick.ts
                price = tick.price
                volume = tick.volume
                tick_type = tick.tick_type
                original_tick_type = tick_type  # already normalized by adapter
                exchange_dt = tick.exchange_dt
                self.indicators.last_tick_price = price  # minimal side effect for inference path
            else:
                ts, price, volume, tick_type, original_tick_type = self._parse_tick_locked(
                    tick
                )
                exchange_dt = getattr(tick, "datetime", None) or (
                    self._last_tick_exchange_dt or datetime.datetime.fromtimestamp(ts)
                )

            self._record_tick_arrival_locked(ts, exchange_dt, tick_type)
            self._telemetry.record_atr(self.indicators.current_atr)
            self._maybe_refresh_atr(ts)
            self.indicators.update_vwap(ts, price, volume)
            self.indicators.update_momentum(ts, volume, tick_type)
            if self.has_position:
                self.ticks_since_entry += 1
                if self._resynced_position:
                    self._calibrate_trailing_peak_after_resync(price)
                self._update_trailing_peak(price)

            # Kernel force-flatten (owned by host for hard session boundary safety).
            # Runs before normal strategy decision so force exit has priority.
            dt_for_risk = exchange_dt or tick.datetime if not isinstance(tick, TickSnapshot) else exchange_dt
            signal = self._maybe_kernel_force_flatten(ts, price, dt_for_risk)
            if signal is None:
                signal = self.process_strategy(ts, price, dt_for_risk)

            if signal is not None:
                if signal.intent == "entry":
                    self._pending_intent_cancel_exchange_dt = dt_for_risk
                    self._telemetry.record_entry_signal()
                elif signal.intent == "exit":
                    self._telemetry.record_exit_signal()
                self._arm_pending(signal)
                self._log_signal_audit(signal)

        self._archive.enqueue_tick(tick, tick_type)

        if volume >= 20:
            logger.debug(
                "Tick | Price:%.1f | Vol:%d | Type:%d (orig=%d)",
                price,
                volume,
                tick_type,
                original_tick_type,
            )

        if signal is not None:
            self._enqueue_order(signal)

    def _maybe_refresh_atr(self, ts: int):
        if ts - self.indicators.last_atr_refresh >= self._cfg.atr_refresh_sec:
            self.indicators.last_atr_refresh = ts
            threading.Thread(target=self.refresh_atr, daemon=True).start()

    def _today(self) -> datetime.date:
        """交易所「今天」：有 tick 時以 tick 日期為準（回測確定性），否則用系統日期。"""
        if self._last_tick_exchange_dt is not None:
            return self._last_tick_exchange_dt.date()
        return datetime.date.today()

    def refresh_atr(self):
        try:
            today = self._today()
            with self.lock:
                current_atr = self.indicators.current_atr
                long_done = self.indicators._atr_long_lookback_date
            start, used_long = self._atr_kline_start(
                today,
                current_atr=current_atr,
                long_lookback_days=self._cfg.atr_kline_lookback_days,
                long_lookback_done_for=long_done,
            )
            kbars = self.api.kbars(
                contract=self.contract,
                start=start.isoformat(),
                end=today.isoformat(),
            )
            atr = IndicatorState.compute_atr(
                kbars, atr_period=self._cfg.atr_period
            )
            # live_get reads sweep-patched config module attributes at runtime.
            _live_trend_enabled = self._cfg.live_get(
                "TREND_FILTER_ENABLED", self._cfg.trend_filter_enabled
            )
            if _live_trend_enabled:
                trend_dir, trend_strength = self._trend_refresh.refresh_trend(
                    kbars,
                    exchange_dt=self._last_tick_exchange_dt,
                    used_long_lookback=used_long,
                    atr=atr,
                    cfg=self._cfg,
                )
            else:
                with self.lock:
                    trend_dir = self.indicators.trend_dir
                    trend_strength = self.indicators.trend_strength
            with self.lock:
                self.indicators.current_atr = atr
                self.indicators.trend_dir = trend_dir
                self.indicators.trend_strength = trend_strength
                if used_long:
                    self.indicators._atr_long_lookback_date = today
            lookback_label = (
                f"{self._cfg.atr_kline_lookback_days}d"
                if used_long
                else "當日"
            )
            logger.info(
                "ATR(%d) 更新: %.2f | start=%s lookback=%s",
                self._cfg.atr_period,
                atr,
                start.isoformat(),
                lookback_label,
            )
            self._log_api_usage("atr_refresh")
            if self._cfg.kbars_archive:
                try:
                    self._archive.archive_kbars(
                        kbars,
                        product_code=self.contract.code,
                        trade_date=today,
                    )
                except Exception as arch_err:
                    logger.warning("Kbars 落盤失敗: %s", arch_err)
        except Exception as e:
            logger.warning("ATR 更新失敗: %s", e)

    def _vol_threshold(self, dt: datetime.datetime) -> tuple[float, float, float]:
        """P1-2: (base_vol, multiplier, vol_threshold)."""
        return self._calendar.compute_vol_threshold(
            self.indicators.current_atr,
            dt,
            base_vol=self._cfg.base_vol,
            atr_vol_mult=self._cfg.atr_vol_mult,
            mult_futures=self._cfg.open_mult_futures,
            mult_spot=self._cfg.open_mult_spot,
            mult_normal=self._cfg.open_mult_normal,
        )

    def _calibrate_trailing_peak_after_resync(self, price: float) -> None:
        """P0-3: 重啟對帳後首 tick，保守初始化 trailing_peak。"""
        old_peak = self.trailing_peak
        if self.position_dir == "Long":
            self.trailing_peak = max(self.entry_price, price)
        elif self.position_dir == "Short":
            self.trailing_peak = min(self.entry_price, price)
        self._resynced_position = False
        logger.info(
            "持倉 peak 校準 | %s entry=%.1f tick=%.1f peak %.1f→%.1f",
            self.position_dir,
            self.entry_price,
            price,
            old_peak,
            self.trailing_peak,
        )

    def _record_tick_arrival_locked(
        self, ts: int, exchange_dt: datetime.datetime, tick_type: int
    ) -> None:
        """Must be called with self.lock held."""
        self.last_tick_exchange_ts = ts
        self._last_tick_wall_time = self._clock()
        self._last_tick_exchange_dt = exchange_dt
        bucket = tick_type if tick_type in self._tick_type_counts else 0
        self._tick_type_counts[bucket] = self._tick_type_counts.get(bucket, 0) + 1
        self._maybe_warn_clock_skew(ts)

    def _record_tick_arrival(
        self, ts: int, exchange_dt: datetime.datetime, tick_type: int
    ) -> None:
        self.last_tick_exchange_ts = ts
        self._last_tick_wall_time = self._clock()
        self._last_tick_exchange_dt = exchange_dt
        bucket = tick_type if tick_type in self._tick_type_counts else 0
        self._tick_type_counts[bucket] = self._tick_type_counts.get(bucket, 0) + 1
        self._maybe_warn_clock_skew(ts)

    def _maybe_warn_clock_skew(self, exchange_ts: int) -> None:
        skew = abs(exchange_ts - self._clock())
        if skew <= self._cfg.clock_skew_warn_sec:
            return
        now = self._clock()
        if now - self._last_clock_skew_warn_wall < 300:
            return
        self._last_clock_skew_warn_wall = now
        logger.warning(
            "系統鐘與交易所時間偏差 %.1fs | 策略決策仍以 tick 時間為準",
            skew,
        )

    def _maybe_log_tick_type_summary(self) -> None:
        """P1-3: 每 30 分鐘輸出 tick_type 分布（UAT 觀測）。"""
        if self._last_tick_exchange_dt is None:
            return
        if not self._calendar.is_trading_session(
            self._last_tick_exchange_dt,
            self._cfg.session_start,
            self._cfg.session_end,
        ):
            return
        now = self._clock()
        if now - self._last_tick_type_log_wall < 1800:
            return
        total = sum(self._tick_type_counts.values())
        if total == 0:
            return
        self._last_tick_type_log_wall = now
        inferred_total = sum(self._tick_type_inferred_counts.values())
        logger.info(
            "tick_type 分布 | type0=%d type1=%d type2=%d total=%d "
            "| type0_pct=%.1f%% | inferred_buy=%d inferred_sell=%d inferred_total=%d",
            self._tick_type_counts.get(0, 0),
            self._tick_type_counts.get(1, 0),
            self._tick_type_counts.get(2, 0),
            total,
            100.0 * self._tick_type_counts.get(0, 0) / total,
            self._tick_type_inferred_counts.get(1, 0),
            self._tick_type_inferred_counts.get(2, 0),
            inferred_total,
        )

    def _check_no_tick_watchdog(self) -> None:
        """P4-8: 交易時段內長時間無 tick → 告警並嘗試重訂閱。"""
        if not self._api_connected or self.contract is None:
            return
        if self._last_tick_exchange_dt is None or self._last_tick_wall_time <= 0:
            return
        if not self._calendar.is_trading_session(
            self._last_tick_exchange_dt,
            self._cfg.session_start,
            self._cfg.session_end,
        ):
            return
        silent = self._clock() - self._last_tick_wall_time
        if silent < self._cfg.no_tick_timeout_sec:
            return
        now = self._clock()
        if now - self._last_no_tick_resubscribe_wall < 60:
            return
        self._last_no_tick_resubscribe_wall = now
        self._telemetry.record_no_tick_resubscribe()
        logger.warning(
            "No-tick 看門狗 | %.0fs 無 tick，嘗試重訂閱 %s",
            silent,
            self.contract.code,
        )
        try:
            if self._resubscribe_ticks is None:
                logger.warning("No-tick 看門狗 | 未設定 tick 重訂閱 hook，略過")
                return
            self._resubscribe_ticks()
            logger.info("No-tick 看門狗 | 重訂閱已送出")
        except Exception as e:
            logger.warning("No-tick 看門狗 | 重訂閱失敗: %s", e)

    def _timeout_loop(self):
        while self._running:
            try:
                self._check_pending_timeout()
                self._check_exit_order_retry()
                self._check_session_watchdog()
                self._check_no_tick_watchdog()
                self._maybe_log_tick_type_summary()
            except Exception as e:
                logger.warning("背景維運檢查異常: %s", e)
            time.sleep(1)

    def _check_session_watchdog(self) -> None:
        with self.lock:
            if self._api_connected:
                return
            disconnected_since = self._disconnect_since
            next_at = self._next_relogin_at
            attempts = self._session_relogin_attempts

        if disconnected_since <= 0:
            return
        now = self._clock()
        if now < next_at:
            return
        if now - disconnected_since < self._cfg.session_watchdog_sec:
            return
        if attempts >= self._cfg.session_relogin_max_attempts:
            self._alerts.send(
                f"Session 重登入已達上限 {self._cfg.session_relogin_max_attempts}",
                level="CRITICAL",
            )
            with self.lock:
                self._next_relogin_at = now + 300.0
            return

        try:
            logger.warning(
                "Session 看門狗觸發重登入 | attempt=%d",
                attempts + 1,
            )
            self.api.login(
                api_key=self._cfg.api_key,
                secret_key=self._cfg.secret_key,
                subscribe_trade=True,
            )
            with self.lock:
                self._session_relogin_attempts = 0
                self._disconnect_since = 0.0
                self._next_relogin_at = 0.0
            self._on_reconnected()
        except Exception as e:
            backoff = self._cfg.session_relogin_backoff_base_sec * (2**attempts)
            logger.error("Session 重登入失敗: %s | backoff=%.1fs", e, backoff)
            self._alerts.send(f"Session 重登入失敗: {e}", level="CRITICAL")
            with self.lock:
                self._session_relogin_attempts = attempts + 1
                self._next_relogin_at = now + backoff

    def _mark_disconnected(self) -> None:
        with self.lock:
            self._api_connected = False
            if self._disconnect_since <= 0:
                self._disconnect_since = self._clock()

    def _clear_pending(self):
        self.is_pending = False
        self.pending_intent = None
        self.exit_pending = False
        self.pending_trade = None
        self.pending_order_id = None
        self.pending_since = 0.0
        self.pending_exchange_ts = 0
        self.pending_qty = 0
        self.pending_signal_price = 0.0
        self.pending_limit_price = 0.0
        self.pending_exit_reason = ""
        self.pending_ioc_slippage = self._cfg.ioc_slippage_points
        self.filled_qty = 0
        self._pending_action = None
        self._exit_order_retry_count = 0
        self._exit_order_retry_at = 0.0

    def handle_session_event(
        self, resp_code: int, event_code: int, info: str, event: str
    ):
        if event_code == 12:
            logger.warning("API 重連中 | resp=%s info=%s", resp_code, info)
            self._mark_disconnected()
        elif event_code == 13:
            logger.info("API 重連成功 | resp=%s", resp_code)
            threading.Thread(
                target=self._on_reconnected, daemon=True, name="reconnect-sync"
            ).start()

    def handle_session_down(self):
        logger.warning("API 連線中斷")
        self._mark_disconnected()

    def _on_reconnected(self):
        """P4-1: 先補查 pending，再對帳持倉，最後重新訂閱。"""
        with self.lock:
            trade = self.pending_trade if self.is_pending else None

        if trade is not None:
            try:
                self._reconcile_pending_trade(trade)
            except Exception as e:
                logger.warning("重連後 pending 補查失敗: %s", e)

        self.sync_positions()

        try:
            if self._resubscribe_ticks is not None:
                self._resubscribe_ticks()
        except Exception as e:
            logger.warning("重連後 subscribe 失敗: %s", e)

        self.refresh_atr()

        with self.lock:
            self._api_connected = True
            self._disconnect_since = 0.0
            self._session_relogin_attempts = 0
            self._next_relogin_at = 0.0

        logger.info("重連後狀態同步完成")

    def run(self) -> None:
        """Broker-neutral blocking run loop (login + live wiring must be done first)."""
        self._running = True

        if self._cfg.tick_archive:
            self._archive.maybe_start_tick_archive(self.contract.code)
            logger.info(
                "Tick 落盤已啟用 | TICK_ARCHIVE=1 | code=%s",
                self.contract.code,
            )

        logger.info(
            "VWAP Momentum 策略已啟動 | config=%s | ATR=%.2f | 模擬=%s",
            self._cfg.config_path,
            self.current_atr,
            self._cfg.simulation,
        )

        threading.Thread(target=self._timeout_loop, daemon=True).start()
        self._start_order_worker()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("策略手動停止")
        finally:
            self._running = False
            if not self._order_sync_mode:
                self._order_queue.put_nowait(None)
            self._archive.shutdown_tick_archive()
            if self._trading_date is not None:
                self._emit_daily_summary(self._trading_date)
            self.api.logout()
            shutdown_async_logging()

    def start(self) -> None:
        """Live Shioaji convenience entry (delegates to ShioajiLiveBootstrap)."""
        from trading_engine.adapters.shioaji_live import ShioajiLiveBootstrap

        ShioajiLiveBootstrap(self).start_live()

