"""P0 atr_stale + P4-13 reconnect warmup / disconnect limits."""

from __future__ import annotations

import datetime
import unittest
from dataclasses import replace
from unittest.mock import MagicMock

from trading_engine.core.runtime_config import RuntimeConfig
from trading_engine.testing.defaults import default_test_settings
from trading_engine.testing.helpers import make_host


class TestAtrStaleAndReconnectGuards(unittest.TestCase):
    def _host_with_cfg(self, **overrides):
        base = replace(default_test_settings(), **overrides)
        host = make_host()
        host._cfg = RuntimeConfig(base)
        return host

    def test_atr_stale_when_never_refreshed_or_too_old(self):
        host = make_host()
        host.indicators.last_atr_refresh = 0.0
        self.assertTrue(host._is_atr_stale(5000))

        host.indicators.last_atr_refresh = 1000.0
        self.assertFalse(host._is_atr_stale(1500))
        self.assertTrue(host._is_atr_stale(2000))

    def test_risk_gate_exposes_stale_and_warmup(self):
        host = make_host()
        host.indicators.last_atr_refresh = 1000.0
        host._reconnect_warmup_until_ts = 2000
        dt = datetime.datetime(2026, 6, 10, 10, 0, 0)
        risk = host._risk_gate(1500, dt)
        self.assertFalse(risk.atr_stale)
        self.assertTrue(risk.reconnect_warmup_active)
        self.assertTrue(host._risk_gate(1700, dt).atr_stale)

    def test_failed_atr_refresh_keeps_success_ts_and_clears_in_flight(self):
        host = make_host()
        host.contract = MagicMock(code="TXFR1")
        host.api.kbars = MagicMock(side_effect=RuntimeError("kbars down"))
        host.last_tick_exchange_ts = 1000
        host.indicators.last_atr_refresh = 500.0

        host._atr_refresh_in_flight = True
        host.refresh_atr()

        self.assertEqual(host.indicators.last_atr_refresh, 500.0)
        self.assertFalse(host._atr_refresh_in_flight)

    def test_disconnect_count_blocks_entry_at_limit(self):
        host = self._host_with_cfg(max_disconnects_per_day=2)
        host._alerts = MagicMock()

        host._mark_disconnected()
        self.assertEqual(host._disconnect_count_today, 1)
        self.assertFalse(host.block_new_entry)

        host._api_connected = True
        host._mark_disconnected()
        self.assertEqual(host._disconnect_count_today, 2)
        self.assertTrue(host.block_new_entry)

    def test_disconnect_with_position_alerts(self):
        host = make_host()
        host.position_qty = 1
        host.position_dir = "Long"
        host._alerts = MagicMock()

        host._mark_disconnected()
        host._alerts.send.assert_called()
        self.assertIn("持倉", host._alerts.send.call_args[0][0])

    def test_repeated_disconnect_events_do_not_increment_while_offline(self):
        host = make_host()
        host._api_connected = False
        host._disconnect_count_today = 1

        host._mark_disconnected()
        self.assertEqual(host._disconnect_count_today, 1)

    def test_reconnect_arms_warmup_on_first_post_reconnect_tick(self):
        host = make_host()
        host._api_connected = False
        host.last_tick_exchange_ts = 5000
        host.contract = MagicMock(code="TXFR1")
        host.sync_positions = MagicMock()
        host.refresh_atr = MagicMock()

        host._on_reconnected()

        self.assertTrue(host._pending_reconnect_warmup)
        self.assertEqual(host._reconnect_warmup_until_ts, 0)
        self.assertTrue(host._api_connected)

        host._arm_reconnect_warmup_on_first_tick_locked(16000)
        self.assertEqual(
            host._reconnect_warmup_until_ts,
            16000 + host._cfg.reconnect_warmup_sec,
        )
        self.assertFalse(host._pending_reconnect_warmup)


if __name__ == "__main__":
    unittest.main()