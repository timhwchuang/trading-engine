"""Order lifecycle: place, pending, fills, retries."""

from __future__ import annotations

import datetime
import threading

from trading_engine.core.audit.signal_audit import format_signal_audit
from trading_engine.core.order_events import is_futures_deal, is_futures_order
from trading_engine.core.trading_state import PendingIntent
from trading_engine.core.types import OrderSignal
from trading_engine.logging_setup import get_logger
from trading_engine.order_errors import OrderErrorCategory, classify_order_error, should_retry_order

logger = get_logger()


class OrderExecutorMixin:
    def _validate_order_signal(self, signal: OrderSignal) -> bool:
        """Reject invalid strategy/kernel signals before arming pending."""
        if signal.qty <= 0:
            logger.warning("拒絕 OrderSignal: qty=%s 必須 > 0", signal.qty)
            return False
        if signal.intent not in ("entry", "exit"):
            logger.warning("拒絕 OrderSignal: 非法 intent=%r", signal.intent)
            return False
        if signal.action not in ("Buy", "Sell"):
            logger.warning("拒絕 OrderSignal: 非法 action=%r", signal.action)
            return False
        if self.is_pending:
            logger.warning(
                "拒絕 OrderSignal: 已有 pending (intent=%s)",
                self.pending_intent,
            )
            return False
        if signal.intent == "entry":
            if self.block_new_entry:
                logger.warning("拒絕 entry OrderSignal: block_new_entry=True")
                return False
            if self.position_qty > 0:
                logger.warning(
                    "拒絕 entry OrderSignal: 已有持倉 qty=%s",
                    self.position_qty,
                )
                return False
        if signal.intent == "exit" and self.position_qty <= 0:
            logger.warning("拒絕 exit OrderSignal: 無持倉")
            return False
        return True

    def _arm_pending(self, signal: OrderSignal) -> None:
        """P2-2: lock 內同步設 pending，堵住雙 tick 雙單。"""
        self.is_pending = True
        self.pending_intent = signal.intent
        self.pending_exchange_ts = signal.exchange_ts
        self.pending_qty = signal.qty
        self.pending_signal_price = signal.ref_price
        self.pending_ioc_slippage = (
            signal.slippage_points
            if signal.slippage_points is not None
            else self._cfg.ioc_slippage_points
        )
        self._pending_action = signal.action
        is_buy = signal.action == "Buy"
        self.pending_limit_price = self._telemetry.compute_limit_price(
            signal.ref_price,
            is_buy=is_buy,
            ioc_slippage=self.pending_ioc_slippage,
        )
        self.pending_exit_reason = (
            signal.audit.reason
            if signal.audit is not None and signal.intent == PendingIntent.EXIT
            else ""
        )
        if signal.intent == PendingIntent.EXIT:
            self.exit_pending = True

        # Phase 4 defensive guard (logs only)
        try:
            from trading_engine.core.trading_state import validate_pending_consistency

            validate_pending_consistency(
                is_pending=self.is_pending,
                pending_intent=self.pending_intent,
                exit_pending=self.exit_pending,
                position_qty=self.position_qty,
                position_dir=self.position_dir,
                logger=logger,
            )
        except Exception:
            pass  # never let guard break hot path

    @staticmethod
    def _log_signal_audit(signal: OrderSignal) -> None:
        if signal.audit is None:
            return
        logger.info("SIGNAL_AUDIT %s", format_signal_audit(signal.audit))

    def _update_trailing_peak(self, price: float):
        """持倉後 trailing stop 用 peak，僅在 manage_exit 邏輯內使用。"""
        if self.position_dir == "Long":
            self.trailing_peak = max(self.trailing_peak, price)
        elif self.position_dir == "Short":
            self.trailing_peak = min(self.trailing_peak, price)

    def is_trading_session(self, dt: datetime.datetime) -> bool:
        return self._calendar.is_trading_session(dt, self._cfg.session_start, self._cfg.session_end)

    def _maybe_reset_daily_state(self, dt: datetime.datetime) -> None:
        """P0-8: 交易日變更時重置日內風控（日盤 = 日曆日，見 exchange_time）。"""
        trade_date = self._calendar.trading_day_for_daily_reset(dt)
        if self._trading_date is None:
            self._trading_date = trade_date
            return
        if trade_date == self._trading_date:
            return
        logger.info(
            "交易日切換 %s → %s，重置日內風控",
            self._trading_date,
            trade_date,
        )
        self._emit_daily_summary(self._trading_date)
        self._reset_daily_state()
        self._telemetry.reset()
        self._tick_type_counts = {0: 0, 1: 0, 2: 0}
        self._tick_type_inferred_counts = {1: 0, 2: 0}
        self._trading_date = trade_date

    def _reset_daily_state(self) -> None:
        self.daily_pnl = 0.0
        self.block_new_entry = False
        self.consecutive_loss = 0

    def _emit_daily_summary(self, trade_date: datetime.date) -> None:
        self._telemetry.snapshot_tick_types(self._tick_type_counts)
        self._telemetry.update_risk_state(self.daily_pnl, self.consecutive_loss)
        summary = self._telemetry.build_summary(trade_date.isoformat())
        logger.info("DAILY_SUMMARY %s", self._telemetry.format_daily_summary(summary))

    def process_strategy(self, ts: int, price: float, dt: datetime.datetime) -> OrderSignal | None:
        self._maybe_reset_daily_state(dt)
        market = self.indicators.snapshot(ts, price, dt)
        vol_threshold = self._vol_threshold(dt)
        signal, effects = self.strategy.evaluate(
            market,
            self._position_snapshot(),
            self._risk_gate(ts, dt),
            vol_threshold,
            session_force_flatten_time=self._cfg.session_force_flatten_time,
            max_daily_loss_points=self._cfg.max_daily_loss_points,
            on_daily_loss_block=lambda: logger.warning("觸發單日最大虧損，停止新進場"),
        )
        if effects.block_new_entry:
            self.block_new_entry = True
        return signal

    def reset_strategy_state(self) -> None:
        """Reset strategy episode state after fills / session events."""
        self.strategy.reset()

    def reset_momentum(self) -> None:
        """Backward-compatible alias for ``reset_strategy_state``."""
        self.reset_strategy_state()

    def manage_exit(self, price: float, ts: int) -> OrderSignal | None:
        dt = self._last_tick_exchange_dt or datetime.datetime.fromtimestamp(ts)
        market = self.indicators.snapshot(ts, price, dt)
        signal, _effects = self.strategy.manage_exit(market, self._position_snapshot())
        return signal

    def _maybe_kernel_force_flatten(
        self, ts: int, price: float, dt: datetime.datetime
    ) -> OrderSignal | None:
        """Kernel-owned force flatten at session_force_flatten_time.

        Strategy may return a custom OrderSignal via session_force_flatten_signal
        (for price/slippage/audit customization). If None, kernel synthesizes a
        standard full exit using flatten_slippage_points.
        """
        if self.position_qty <= 0:
            return None
        if self.is_pending or self.exit_pending:
            return None
        risk = self._risk_gate(ts, dt)
        if not risk.force_flatten:
            return None

        market = self.indicators.snapshot(ts, price, dt)
        position = self._position_snapshot()

        # Strategy hook for customization (price, slippage, reason, audit)
        custom, _effects = self.strategy.session_force_flatten_signal(
            market, position, self._cfg.session_force_flatten_time
        )
        if custom is not None:
            # Trust strategy provided signal but ensure intent/qty safety for first version
            if custom.intent != "exit":
                custom = None  # fallthrough to default
            else:
                return custom

        # Default kernel-produced exit (full position, using configured flatten slippage)
        action = "Sell" if self.position_dir == "Long" else "Buy"
        return OrderSignal(
            action=action,
            qty=self.position_qty,
            ref_price=price,
            intent="exit",
            exchange_ts=ts,
            slippage_points=self._cfg.flatten_slippage_points,
            # audit left to None for pure kernel forced; consumers can enrich via telemetry
        )

    def _clear_entry_tracking(self) -> None:
        self.entry_exchange_ts = 0
        self.ticks_since_entry = 0

    def _begin_entry_tracking(self, exchange_ts: int) -> None:
        self.entry_exchange_ts = exchange_ts
        self.ticks_since_entry = 0

    def _activate_vwap_stop_immediately(self) -> None:
        """重啟對帳持倉：進場時間未知，直接啟用 VWAP 停損。"""
        self.entry_exchange_ts = 0
        self.ticks_since_entry = self._cfg.exit_grace_ticks

    def place_order(self, signal: OrderSignal):
        action = signal.action
        qty = signal.qty
        ref_price = signal.ref_price

        try:
            slip = (
                signal.slippage_points
                if signal.slippage_points is not None
                else self._cfg.ioc_slippage_points
            )
            price = ref_price + slip if action == "Buy" else ref_price - slip
            trade = self._order_adapter.place_ioc_limit(
                self.contract,
                action=action,
                qty=qty,
                limit_price=price,
                account=self.api.futopt_account,
            )
            with self.lock:
                self.pending_trade = trade
                self.pending_order_id = str(trade.order.id)
                self.pending_since = self._clock()
                self._exit_order_retry_count = 0
                self._exit_order_retry_at = 0.0
            logger.info(
                "下單 %s %d 口 @ %.1f (%s) | trade=%s",
                action,
                qty,
                price,
                signal.intent,
                trade.order.id,
            )
        except Exception as e:
            self._handle_place_order_failure(signal, e)

    def _handle_place_order_failure(self, signal: OrderSignal, exc: Exception) -> None:
        category = classify_order_error(exc)
        intent = signal.intent
        logger.error(
            "下單失敗 | intent=%s category=%s err=%s",
            intent,
            category.value,
            exc,
        )

        if intent == "entry":
            with self.lock:
                self._clear_pending()
            if category == OrderErrorCategory.FATAL:
                self._alerts.send(f"進場下單致命錯誤: {exc}", level="CRITICAL")
            return

        with self.lock:
            attempt = self._exit_order_retry_count

        if should_retry_order(
            intent=intent,
            category=category,
            attempt=attempt,
            max_retries=self._cfg.exit_order_max_retries,
        ):
            with self.lock:
                self._exit_order_retry_count = attempt + 1
                self._exit_order_retry_at = self._clock() + self._cfg.exit_order_retry_delay_sec
            logger.warning(
                "出場下單將退避重試 | attempt=%d/%d delay=%.1fs",
                attempt + 1,
                self._cfg.exit_order_max_retries,
                self._cfg.exit_order_retry_delay_sec,
            )
            return

        self._alerts.send(
            f"出場下單失敗且重試耗盡 | category={category.value} err={exc}",
            level="CRITICAL",
        )
        with self.lock:
            self.block_new_entry = True
        try:
            self.sync_positions()
        except Exception as sync_err:
            logger.error("出場失敗後對帳異常: %s", sync_err)

    def _reconstruct_pending_signal(self) -> OrderSignal | None:
        with self.lock:
            if not self.is_pending or self.pending_intent != "exit":
                return None
            action = self._pending_action
            if not action:
                action = "Sell" if self.position_dir == "Long" else "Buy"
            # Phase 1: prefer actual position_qty for exit sizing (full flatten policy)
            exit_qty = self.position_qty if self.position_qty > 0 else (self.pending_qty or 1)
            return OrderSignal(
                action,
                exit_qty,
                self.pending_signal_price,
                "exit",
                exchange_ts=self.pending_exchange_ts,
                slippage_points=self.pending_ioc_slippage,
            )

    def _check_exit_order_retry(self) -> None:
        with self.lock:
            retry_at = self._exit_order_retry_at
            if retry_at <= 0 or self._clock() < retry_at:
                return
            self._exit_order_retry_at = 0.0

        signal = self._reconstruct_pending_signal()
        if signal is None:
            return
        logger.info("出場下單退避重試觸發")
        self._enqueue_order(signal)

    def _start_order_worker(self) -> None:
        if self._order_worker_started:
            return
        self._order_worker_started = True
        threading.Thread(
            target=self._order_worker_loop,
            daemon=True,
            name="order-worker",
        ).start()

    def _order_worker_loop(self) -> None:
        while True:
            signal = self._order_queue.get()
            try:
                if signal is None:
                    break
                self.place_order(signal)
            except Exception as e:
                logger.error("Order worker 異常: %s", e)
            finally:
                self._order_queue.task_done()

    def _enqueue_order(self, signal: OrderSignal) -> None:
        """Decouple API place_order from on_tick lock (live: async worker)."""
        if self._order_sync_mode:
            self.place_order(signal)
            return
        self._start_order_worker()
        self._order_queue.put_nowait(signal)

    def _maybe_dump_raw_order_event(self, stat, msg) -> None:
        if not self._cfg.dump_order_events:
            return
        if stat in self._raw_order_evt_dumped:
            return
        self._raw_order_evt_dumped.add(stat)
        logger.info(
            "RAW_ORDER_EVT %s | keys=%s | %r",
            stat,
            list(msg.keys()),
            msg,
        )

    def handle_order_event(self, stat, msg):
        self._maybe_dump_raw_order_event(stat, msg)
        needs_sync = False
        with self.lock:
            if is_futures_order(stat):
                self._handle_futures_order(msg)
            elif is_futures_deal(stat):
                needs_sync = self._handle_futures_deal(msg)
        if needs_sync:
            self.sync_positions()

    def _event_order_id(self, msg: dict) -> str | None:
        trade_id = msg.get("trade_id")
        if trade_id:
            return str(trade_id)
        status = msg.get("status") or {}
        for key in ("id", "order_id"):
            value = status.get(key)
            if value:
                return str(value)
        order = msg.get("order") or {}
        for key in ("id", "order_id"):
            value = order.get(key)
            if value:
                return str(value)
        return None

    def _matches_pending_order(self, msg: dict) -> bool:
        expected = self.pending_order_id
        if not expected:
            return False
        actual = self._event_order_id(msg)
        return actual is not None and actual == expected

    def _handle_futures_order(self, msg):
        op = msg.get("operation", {})
        op_code = op.get("op_code", "")
        op_type = op.get("op_type", "")
        status = msg.get("status", {}).get("status", "")

        logger.info(
            "委託回報 | op=%s code=%s status=%s | order=%s",
            op_type,
            op_code,
            status,
            self._event_order_id(msg),
        )

        if not self.is_pending:
            return
        if not self._matches_pending_order(msg):
            logger.warning(
                "忽略非當前委託狀態回報 | expected=%s got=%s",
                self.pending_order_id,
                self._event_order_id(msg),
            )
            return

        if op_code and op_code != "00":
            logger.warning("委託失敗: %s", op.get("op_msg", op_code))
            self._clear_pending()
            return

        if status in ("Cancelled", "Failed") or op_type in ("Cancel", "Delete"):
            deal_qty = msg.get("status", {}).get("deal_quantity", 0)
            if deal_qty == 0:
                if self.pending_intent == PendingIntent.ENTRY:
                    tag = "intent_cancelled"
                    if (
                        self._pending_intent_cancel_exchange_dt is not None
                        and self._calendar.is_opening_session_window(
                            self._pending_intent_cancel_exchange_dt
                        )
                    ):
                        tag = "intent_cancelled_open_session"
                    self._telemetry.record_intent_cancelled(tag)
                    logger.info(
                        "委託未成交/已取消，重置 pending | tag=%s",
                        tag,
                    )
                else:
                    logger.info("委託未成交/已取消，重置 pending")
                self._clear_pending()

    def _handle_futures_deal(self, msg) -> bool:
        price = float(msg["price"])
        qty = int(msg["quantity"])
        action = msg.get("action", "")
        order_id = self._event_order_id(msg)
        logger.info(
            "成交回報 | %s %d 口 @ %.1f | order=%s",
            action,
            qty,
            price,
            order_id,
        )

        if not self.is_pending:
            logger.warning("忽略非 pending 成交回報 | order=%s", order_id)
            return False
        if not self._matches_pending_order(msg):
            logger.warning(
                "忽略非當前委託成交回報 | expected=%s got=%s",
                self.pending_order_id,
                order_id,
            )
            return False

        is_buy = self._is_buy_action(action)
        return self._apply_deal_fill(price, is_buy, deal_qty=qty)

    def _apply_deal_fill(self, price: float, is_buy: bool, deal_qty: int = 1) -> bool:
        """套用成交。回傳 True 表示須在 lock 外呼叫 sync_positions()。"""
        expected = self.pending_qty if self.pending_qty > 0 else 1
        if deal_qty > expected:
            logger.warning(
                "成交口數超過 pending | deal=%d expected=%d order=%s",
                deal_qty,
                expected,
                self.pending_order_id,
            )
        self.filled_qty = getattr(self, "filled_qty", 0) + deal_qty
        if self.filled_qty > expected:
            logger.warning(
                "累計成交超過 pending | filled=%d expected=%d order=%s",
                self.filled_qty,
                expected,
                self.pending_order_id,
            )
        if self.filled_qty < expected:
            logger.info(
                "部分成交進度 | intent=%s %d/%d (deal=%d) order=%s | pending 持續（IOC 未結束不全解鎖）",
                self.pending_intent,
                self.filled_qty,
                expected,
                deal_qty,
                self.pending_order_id,
            )
            return False  # keep pending for more fills or cancel

        intent = self.pending_intent
        order_id = self.pending_order_id or ""
        direction = "Buy" if is_buy else "Sell"
        if intent == PendingIntent.ENTRY:
            if self.has_position:
                logger.warning(
                    "STATE_GUARD unexpected entry fill while positioned | qty=%d dir=%s order=%s",
                    self.position_qty,
                    self.position_dir,
                    order_id,
                )
            self.position_qty = self.filled_qty  # Phase 1: use accumulated filled for this pending
            self.entry_price = price
            self.position_dir = "Long" if is_buy else "Short"
            self.trailing_peak = price
            self._begin_entry_tracking(self.pending_exchange_ts)
            fill_audit = self._telemetry.record_fill(
                intent="entry",
                direction=direction,
                signal_price=self.pending_signal_price,
                fill_price=price,
                is_buy=is_buy,
                limit_price=self.pending_limit_price,
                order_id=order_id,
                ts=self.pending_exchange_ts,
                ioc_slippage_allowed=self.pending_ioc_slippage,
            )
            logger.info("FILL_AUDIT %s", self._telemetry.format_fill_audit(fill_audit))
            self.reset_strategy_state()
            self._clear_pending()
            logger.info("進場完成 | %s %d口 @ %.1f", self.position_dir, self.position_qty, price)
            return False

        elif intent == PendingIntent.EXIT and self.has_position:
            if self.position_dir == "Long":
                pnl = price - self.entry_price
            else:
                pnl = self.entry_price - price

            hold_sec = 0
            if self.entry_exchange_ts > 0:
                hold_sec = max(0, self.pending_exchange_ts - self.entry_exchange_ts)

            self.daily_pnl += pnl
            if pnl < 0:
                self.consecutive_loss += 1
            else:
                self.consecutive_loss = 0

            fill_audit = self._telemetry.record_fill(
                intent="exit",
                direction=direction,
                signal_price=self.pending_signal_price,
                fill_price=price,
                is_buy=is_buy,
                limit_price=self.pending_limit_price,
                order_id=order_id,
                ts=self.pending_exchange_ts,
                ioc_slippage_allowed=self.pending_ioc_slippage,
                exit_reason=self.pending_exit_reason,
                pnl_points=pnl,
                hold_sec=hold_sec,
            )
            self._telemetry.update_risk_state(self.daily_pnl, self.consecutive_loss)
            logger.info("FILL_AUDIT %s", self._telemetry.format_fill_audit(fill_audit))

            self.position_qty = 0
            self.position_dir = "Flat"
            self.entry_price = 0.0
            self.trailing_peak = 0.0
            self._clear_entry_tracking()
            self.last_exit_time = self.pending_exchange_ts
            self._clear_pending()
            logger.info(
                "平倉完成 | PnL=%.1f | 今日=%.1f | 連續虧損=%d",
                pnl,
                self.daily_pnl,
                self.consecutive_loss,
            )
            return False

        if intent == PendingIntent.EXIT and not self.has_position:
            logger.warning(
                "STATE_GUARD unexpected exit fill while flat | order=%s",
                order_id,
            )

        # Phase 4: light state guard after fill (defensive logging)
        try:
            from trading_engine.core.trading_state import validate_pending_consistency

            validate_pending_consistency(
                is_pending=self.is_pending,
                pending_intent=self.pending_intent,
                exit_pending=self.exit_pending,
                position_qty=getattr(self, "position_qty", 0),
                position_dir=getattr(self, "position_dir", "Flat"),
                logger=logger,
            )
        except Exception:
            pass

        return False

    @staticmethod
    def _is_buy_action(action) -> bool:
        if action == "Buy":
            return True
        name = getattr(action, "name", None)
        return name == "Buy"

    def _extract_fill_from_trade(self, trade) -> tuple[float, bool] | None:
        deals = getattr(trade.status, "deals", None) or []
        if deals:
            deal = deals[-1]
            return float(deal.price), self._is_buy_action(deal.action)

        deal_qty = int(getattr(trade.status, "deal_quantity", 0) or 0)
        if deal_qty > 0:
            return float(trade.order.price), self._is_buy_action(trade.order.action)
        return None

    def _still_own_pending(self, trade) -> bool:
        """須在 lock 內呼叫：確認 pending 仍屬於此 trade。"""
        return (
            self.is_pending
            and self.pending_order_id is not None
            and self.pending_order_id == str(trade.order.id)
        )

    def _reconcile_pending_trade(self, trade) -> bool:
        """補查委託狀態。回傳 True 表示 pending 已處理完畢（含 callback 已搶先處理）。"""
        try:
            self.api.update_status(trade=trade)
        except Exception as e:
            logger.warning("update_status 補查失敗: %s", e)
            return False

        status = str(getattr(trade.status, "status", "") or "")
        deal_qty = int(getattr(trade.status, "deal_quantity", 0) or 0)
        fill = self._extract_fill_from_trade(trade)

        if fill and deal_qty > 0 and status in ("Filled", "PartFilled"):
            price, is_buy = fill
            needs_sync = False
            with self.lock:
                if not self._still_own_pending(trade):
                    return True
                logger.info("補查確認成交 | status=%s qty=%d", status, deal_qty)
                needs_sync = self._apply_deal_fill(price, is_buy, deal_qty=deal_qty)
            if needs_sync:
                self.sync_positions()
            return True

        if status in ("Cancelled", "Failed") and deal_qty == 0:
            with self.lock:
                if not self._still_own_pending(trade):
                    return True
                logger.info("補查確認委託未成交/已取消，重置 pending")
                self._clear_pending()
            return True

        if not self._cfg.simulation:
            try:
                records = self.api.order_deal_records()
            except Exception as e:
                logger.warning("order_deal_records 補查失敗: %s", e)
                records = []

            order_id = str(trade.order.id)
            for state, event in records:
                if not is_futures_deal(state):
                    continue
                if str(event.get("trade_id", "")) != order_id:
                    continue
                needs_sync = False
                with self.lock:
                    if not self._still_own_pending(trade):
                        return True
                    logger.info("order_deal_records 補查到成交")
                    needs_sync = self._handle_futures_deal(event)
                if needs_sync:
                    self.sync_positions()
                return True

        return False

    def _check_pending_timeout(self):
        with self.lock:
            if not self.is_pending:
                return
            if self._clock() - self.pending_since < self._cfg.pending_timeout_sec:
                return
            trade = self.pending_trade

        if trade is None:
            with self.lock:
                if self.is_pending:
                    logger.warning("Pending 超時但無 trade 物件，重置 pending")
                    self._clear_pending()
            return

        resolved = self._reconcile_pending_trade(trade)
        with self.lock:
            if not self.is_pending:
                return
            if resolved:
                return
            if not self._still_own_pending(trade):
                return
            logger.warning(
                "Pending 超時 %.0fs 且補查無結果，重置 pending",
                self._cfg.pending_timeout_sec,
            )
            intent = self.pending_intent
            self._clear_pending()
        self._alerts.send(
            f"Pending 超時無回報（intent={intent or 'unknown'}）| timeout={self._cfg.pending_timeout_sec}s",
            level="CRITICAL",
        )
        try:
            self.sync_positions()
        except Exception as e:
            logger.error("Pending 超時後對帳失敗: %s", e)
        with self.lock:
            self.block_new_entry = True
