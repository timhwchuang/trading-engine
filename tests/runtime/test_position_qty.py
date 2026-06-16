"""Phase 1 + 6: position_qty accounting, partials (within pending), sync, full exit flatten."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from trading_engine.core.order_events import FUTURES_DEAL
from trading_engine.testing.helpers import (
    arm_pending_entry,
    arm_pending_exit,
    make_broker_with_positions,
    make_host,
)


class TestPositionQty(unittest.TestCase):
    def test_entry_full_sets_qty_from_filled(self):
        host = make_host()
        arm_pending_entry(host, order_id="e1", qty=3, exchange_ts=1000)

        msg = {"price": "18005", "quantity": 3, "action": "Buy", "trade_id": "e1"}
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertEqual(host.position_qty, 3)
        self.assertTrue(host.has_position)
        self.assertEqual(host.position_dir, "Long")

    def test_partial_entry_keeps_pending_and_does_not_set_position_yet(self):
        host = make_host()
        arm_pending_entry(host, order_id="e-part", qty=2)

        msg = {"price": "18005", "quantity": 1, "action": "Buy", "trade_id": "e-part"}
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertTrue(host.is_pending)
        self.assertEqual(host.filled_qty, 1)
        self.assertEqual(host.position_qty, 0)  # not yet applied
        self.assertFalse(host.has_position)

    def test_exit_full_flattens_qty_to_zero(self):
        host = make_host()
        arm_pending_exit(host, order_id="x1", qty=2)
        host.position_qty = 2
        host.position_dir = "Long"
        host.entry_price = 18000.0

        msg = {"price": "18020", "quantity": 2, "action": "Sell", "trade_id": "x1"}
        host.handle_order_event(FUTURES_DEAL, msg)

        self.assertEqual(host.position_qty, 0)
        self.assertFalse(host.has_position)
        self.assertEqual(host.position_dir, "Flat")

    def test_sync_positions_writes_qty_from_broker(self):
        broker = make_broker_with_positions(
            {"code": "TXFR1", "quantity": 5, "direction": "Buy", "price": 17950.0}
        )
        host = make_host(api=broker)
        host.contract = MagicMock(code="TXFR1")

        host.sync_positions(force_resync=True)

        self.assertEqual(host.position_qty, 5)
        self.assertEqual(host.position_dir, "Long")
        self.assertEqual(host.entry_price, 17950.0)

    def test_sync_positions_to_flat_writes_qty_zero(self):
        broker = make_broker_with_positions()  # empty
        host = make_host(api=broker)
        host.contract = MagicMock(code="TXFR1")
        host.position_qty = 3
        host.position_dir = "Short"

        host.sync_positions(force_resync=True)

        self.assertEqual(host.position_qty, 0)
        self.assertEqual(host.position_dir, "Flat")

    def test_position_snapshot_includes_qty(self):
        host = make_host()
        host.position_qty = 4
        host.position_dir = "Short"
        host.entry_price = 18100.0

        snap = host._position_snapshot()
        self.assertEqual(snap.qty, 4)
        self.assertEqual(snap.position_dir, "Short")
        self.assertTrue(snap.has_position)
