"""Phase 6 adversarial callback / deal scenarios."""

from __future__ import annotations

import unittest

from trading_engine.core.order_events import FUTURES_DEAL, FUTURES_ORDER
from trading_engine.testing.helpers import arm_pending_entry, make_host


class TestAdversarialCallbacks(unittest.TestCase):
    def test_duplicate_deal_is_ignored_after_clear(self):
        host = make_host()
        arm_pending_entry(host, order_id="dup-1")
        msg = {"price": "18010", "quantity": 1, "action": "Buy", "trade_id": "dup-1"}

        host.handle_order_event(FUTURES_DEAL, msg)
        self.assertEqual(host.position_qty, 1)

        # Replay the same deal after position applied — should be ignored (no crash, qty not double counted)
        host.handle_order_event(FUTURES_DEAL, msg)
        self.assertEqual(host.position_qty, 1)

    def test_wrong_order_id_deal_ignored_even_when_pending(self):
        host = make_host()
        arm_pending_entry(host, order_id="good")
        bad = {"price": "18010", "quantity": 1, "action": "Buy", "trade_id": "bad-id"}

        host.handle_order_event(FUTURES_DEAL, bad)

        self.assertTrue(host.is_pending)
        self.assertEqual(host.position_qty, 0)

    def test_entry_deal_while_flat_but_no_pending_is_ignored(self):
        host = make_host()
        # No pending armed
        msg = {"price": "18010", "quantity": 1, "action": "Buy", "trade_id": "orphan"}

        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertEqual(host.position_qty, 0)
        self.assertFalse(host.has_position)

    def test_second_deal_while_pending_different_order_ignored(self):
        host = make_host()
        arm_pending_entry(host, order_id="first", qty=1)
        second = {"price": "18011", "quantity": 1, "action": "Buy", "trade_id": "second"}

        host.handle_order_event(FUTURES_DEAL, second)

        self.assertTrue(host.is_pending)
        self.assertEqual(host.position_qty, 0)

    def test_order_event_cancelled_clears_pending(self):
        host = make_host()
        arm_pending_entry(host, order_id="c1")

        cancel_msg = {
            "operation": {"op_code": "00", "op_type": "Cancel"},
            "status": {"status": "Cancelled", "deal_quantity": 0},
            "trade_id": "c1",
        }
        host.handle_order_event(FUTURES_ORDER, cancel_msg)

        self.assertFalse(host.is_pending)
        self.assertEqual(host.position_qty, 0)
