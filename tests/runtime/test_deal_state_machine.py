"""P2-8: FuturesDeal-driven state machine tests with mock API."""

from __future__ import annotations

import unittest

from trading_engine.core.order_events import FUTURES_DEAL
from trading_engine.testing.helpers import arm_pending_entry, arm_pending_exit, make_host


class TestDealStateMachine(unittest.TestCase):
    def test_entry_deal_updates_position(self):
        host = make_host()
        arm_pending_entry(host, exchange_ts=1000)

        msg = {
            "price": "18000",
            "quantity": 1,
            "action": "Buy",
            "trade_id": "ord-entry-1",
        }
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertFalse(host.is_pending)
        self.assertTrue(host.has_position)
        self.assertEqual(host.position_qty, 1)
        self.assertEqual(host.position_dir, "Long")
        self.assertEqual(host.entry_price, 18000.0)
        self.assertEqual(host.entry_exchange_ts, 1000)
        self.assertEqual(host.ticks_since_entry, 0)

    def test_wrong_order_id_ignored(self):
        host = make_host()
        arm_pending_entry(host, order_id="ord-a")

        msg = {
            "price": "18000",
            "quantity": 1,
            "action": "Buy",
            "trade_id": "ord-b",
        }
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertTrue(host.is_pending)
        self.assertFalse(host.has_position)

    def test_exit_deal_clears_position_and_updates_pnl(self):
        host = make_host()
        arm_pending_exit(host, exchange_ts=2000, exit_reason="take_profit", qty=1)
        host.position_qty = 1
        host.position_dir = "Long"
        host.entry_price = 18000.0
        host.trailing_peak = 18010.0
        host.entry_exchange_ts = 1000
        host.ticks_since_entry = 80

        msg = {
            "price": "18020",
            "quantity": 1,
            "action": "Sell",
            "trade_id": "ord-exit-1",
        }
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertFalse(host.is_pending)
        self.assertFalse(host.has_position)
        self.assertEqual(host.position_qty, 0)
        self.assertEqual(host.daily_pnl, 20.0)
        self.assertEqual(host.entry_exchange_ts, 0)
        self.assertEqual(host.ticks_since_entry, 0)


if __name__ == "__main__":
    unittest.main()
