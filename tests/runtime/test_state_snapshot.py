"""Tests for TradingEngine.get_state_snapshot()."""

from __future__ import annotations

import unittest

from trading_engine.core.types import EngineStateSnapshot
from trading_engine.testing.helpers import arm_pending_entry, make_host


class TestStateSnapshot(unittest.TestCase):
    def test_snapshot_matches_engine_fields(self):
        host = make_host()
        host.position_qty = 2
        host.position_dir = "Long"
        host.entry_price = 18000.0
        host.daily_pnl = -5.0
        host.block_new_entry = True
        host._api_connected = False

        snap = host.get_state_snapshot()
        self.assertIsInstance(snap, EngineStateSnapshot)
        self.assertEqual(snap.position_qty, 2)
        self.assertEqual(snap.position_dir, "Long")
        self.assertEqual(snap.entry_price, 18000.0)
        self.assertEqual(snap.daily_pnl, -5.0)
        self.assertTrue(snap.block_new_entry)
        self.assertFalse(snap.api_connected)
        self.assertTrue(snap.has_position)

    def test_snapshot_frozen(self):
        host = make_host()
        snap = host.get_state_snapshot()
        with self.assertRaises(Exception):
            snap.position_qty = 99  # type: ignore[misc]

    def test_snapshot_reflects_pending(self):
        host = make_host()
        arm_pending_entry(host, qty=3)
        snap = host.get_state_snapshot()
        self.assertTrue(snap.is_pending)
        self.assertEqual(snap.pending_intent, "entry")
        self.assertEqual(snap.pending_qty, 3)


if __name__ == "__main__":
    unittest.main()
