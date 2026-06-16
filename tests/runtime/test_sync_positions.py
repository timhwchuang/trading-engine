"""Phase 6: sync_positions behavior (no shioaji import, multi-position selection)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from trading_engine.testing.helpers import make_broker_with_positions, make_host


class TestSyncPositions(unittest.TestCase):
    def test_sync_does_not_require_shioaji_installed(self):
        # This test would fail to even construct the mock if position_normalizer leaked imports badly
        broker = make_broker_with_positions(
            {"code": "TXFR1", "quantity": 1, "direction": "Sell", "price": 18050}
        )
        host = make_host(api=broker)
        host.contract = MagicMock(code="TXFR1")

        host.sync_positions()

        self.assertEqual(host.position_qty, 1)
        self.assertEqual(host.position_dir, "Short")

    def test_multiple_open_positions_takes_first_matching_code(self):
        broker = make_broker_with_positions(
            {"code": "OTHER", "quantity": 10, "direction": "Buy", "price": 100},
            {"code": "TXFR1", "quantity": 2, "direction": "Buy", "price": 17900},
        )
        host = make_host(api=broker)
        host.contract = MagicMock(code="TXFR1")

        host.sync_positions()

        self.assertEqual(host.position_qty, 2)  # first match wins per current impl

    def test_zero_quantity_positions_are_ignored(self):
        broker = make_broker_with_positions(
            {"code": "TXFR1", "quantity": 0, "direction": "Buy", "price": 1},
            {"code": "TXFR1", "quantity": 0},
        )
        host = make_host(api=broker)
        host.contract = MagicMock(code="TXFR1")
        host.position_qty = 99

        host.sync_positions()

        # Should go flat because no non-zero matched
        self.assertEqual(host.position_qty, 0)
