"""Session management: login, reconnect, watchdog."""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from typing import Any, Optional

from trading_engine.logging_setup import setup_async_logging

logger = setup_async_logging()


class SessionMixin:
    def _activate_ca(self) -> None:
        """P4-10: 先無 person_id；失敗則以 env / 帳號 person_id 重試。"""
        try:
            if self.api.activate_ca(
                ca_path=self._cfg.ca_path, ca_passwd=self._cfg.ca_passwd
            ):
                logger.info("CA 憑證啟用成功")
                return
        except Exception as e:
            logger.warning("CA 啟用失敗（無 person_id）: %s", e)

        person_id = os.environ.get("SJ_CA_PERSON_ID") or getattr(
            self.api.futopt_account, "person_id", None
        )
        if not person_id:
            raise RuntimeError(
                "CA 憑證啟用失敗；請設定 SJ_CA_PERSON_ID 或確認券商帳號 person_id"
            )

        if not self.api.activate_ca(
            ca_path=self._cfg.ca_path,
            ca_passwd=self._cfg.ca_passwd,
            person_id=person_id,
        ):
            raise RuntimeError(f"CA 憑證啟用失敗（person_id={person_id}）")
        logger.info("CA 憑證啟用成功（person_id）")

    def _require_futopt_account(self) -> None:
        if self.api.futopt_account is None:
            raise RuntimeError(
                "無期貨帳號，請確認帳號已開通期貨並完成簽署"
            )

    def login(self):
        self.api.login(
            api_key=self._cfg.api_key,
            secret_key=self._cfg.secret_key,
            subscribe_trade=True,
        )
        self._require_futopt_account()
        self.contract = self._resolve_contract()
        logger.info(
            "登入成功 | 合約: %s | 模擬: %s | 帳號: %s",
            self.contract.code,
            self._cfg.simulation,
            getattr(self.api.futopt_account, "account_id", "N/A"),
        )

        if not self._cfg.simulation:
            if not self._cfg.ca_path or not self._cfg.ca_passwd:
                raise RuntimeError("正式模式需設定 SJ_CA_PATH 與 SJ_CA_PASSWD")
            self._activate_ca()
            self.api.subscribe_trade(self.api.futopt_account)

        self.sync_positions(force_resync=True)
        self.refresh_atr()
        self._log_api_usage("login")

    @staticmethod
    def _atr_kline_start(
        today: datetime.date,
        *,
        current_atr: float,
        long_lookback_days: int,
        long_lookback_done_for: Optional[datetime.date],
    ) -> tuple[datetime.date, bool]:
        """P4-9: 開盤/ATR=0 用長 lookback；盤中僅抓當日 K 線。"""
        if current_atr <= 0 or long_lookback_done_for != today:
            return today - datetime.timedelta(days=long_lookback_days), True
        return today, False

    def _log_api_usage(self, context: str) -> None:
        try:
            usage = self.api.usage()
        except Exception as e:
            logger.warning("API usage 查詢失敗 (%s): %s", context, e)
            return

        logger.info(
            "API usage [%s] | bytes=%s limit=%s remaining=%s connections=%s",
            context,
            usage.bytes,
            usage.limit_bytes,
            usage.remaining_bytes,
            usage.connections,
        )
        if (
            usage.limit_bytes > 0
            and usage.remaining_bytes < usage.limit_bytes * 0.1
        ):
            logger.warning(
                "API 流量剩餘 < 10%% | remaining=%s limit=%s",
                usage.remaining_bytes,
                usage.limit_bytes,
            )

    def _contract_position_codes(self) -> set:
        codes = {self.contract.code}
        for attr in ("target_code", "symbol"):
            value = getattr(self.contract, attr, None)
            if value:
                codes.add(value)
        return codes

    def _position_matches_contract(self, pos) -> bool:
        return pos.code in self._contract_position_codes()

    def sync_positions(self, *, force_resync: bool = False):
        """啟動時從券商同步持倉，避免重啟後策略與實際部位脫節。"""
        try:
            positions = self.api.list_positions(account=self.api.futopt_account)
        except Exception as e:
            logger.warning("持倉對帳失敗: %s", e)
            return

        matched = None
        for pos in positions:
            if int(pos.quantity) == 0:
                continue
            if self._position_matches_contract(pos):
                matched = pos
                break

        with self.lock:
            if matched is None:
                self.position_qty = 0
                self.position_dir = "Flat"
                self.entry_price = 0.0
                self.trailing_peak = 0.0
                self._clear_entry_tracking()
                open_positions = [
                    p for p in positions if int(p.quantity) != 0
                ]
                if open_positions:
                    logger.warning(
                        "券商有 %d 筆持倉，但無法對應合約 %s（%s）",
                        len(open_positions),
                        self.contract.code,
                        ", ".join(p.code for p in open_positions),
                    )
                else:
                    logger.info("持倉對帳 | 無持倉")
                return

            from trading_engine.adapters.position_normalizer import is_long_direction

            is_long = is_long_direction(matched.direction)
            new_dir = "Long" if is_long else "Short"
            had_position = self.position_qty > 0
            same_direction = had_position and self.position_dir == new_dir
            preserve_peak = (
                had_position and same_direction and not force_resync
            )

            self.position_qty = int(matched.quantity)
            self.position_dir = new_dir
            self.entry_price = float(matched.price)
            if preserve_peak:
                logger.info(
                    "持倉對帳 | 保留 trailing_peak=%.1f | %s %d口 @ %.1f",
                    self.trailing_peak,
                    self.position_dir,
                    matched.quantity,
                    self.entry_price,
                )
            else:
                self.trailing_peak = self.entry_price
                self._resynced_position = True
            self._activate_vwap_stop_immediately()
            self.reset_strategy_state()
            if not preserve_peak:
                logger.info(
                    "持倉對帳 | %s %d口 @ %.1f | code=%s | peak 待首 tick 校準",
                    self.position_dir,
                    matched.quantity,
                    self.entry_price,
                    matched.code,
                )

    def _resolve_contract(self):
        txf = getattr(self.api.Contracts.Futures, "TXF", None)
        code = self._cfg.product_code
        if txf is not None and hasattr(txf, code):
            return getattr(txf, code)
        return self.api.Contracts.Futures[code]

