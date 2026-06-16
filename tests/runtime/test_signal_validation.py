"""Tests for _validate_order_signal guards."""

from __future__ import annotations

import unittest

from trading_engine.core.types import OrderSignal
from trading_engine.testing.helpers import arm_pending_entry, make_host


class TestSignalValidation(unittest.TestCase):
    def test_rejects_non_positive_qty(self):
        host = make_host()
        bad = OrderSignal("Buy", 0, 18000.0, "entry", exchange_ts=1)
        self.assertFalse(host._validate_order_signal(bad))

    def test_rejects_invalid_intent(self):
        host = make_host()
        bad = OrderSignal("Buy", 1, 18000.0, "flip", exchange_ts=1)
        self.assertFalse(host._validate_order_signal(bad))

    def test_rejects_entry_when_pending(self):
        host = make_host()
        arm_pending_entry(host)
        signal = OrderSignal("Buy", 1, 18000.0, "entry", exchange_ts=2)
        self.assertFalse(host._validate_order_signal(signal))

    def test_rejects_entry_when_block_new_entry(self):
        host = make_host()
        host.block_new_entry = True
        signal = OrderSignal("Buy", 1, 18000.0, "entry", exchange_ts=1)
        self.assertFalse(host._validate_order_signal(signal))

    def test_rejects_exit_when_flat(self):
        host = make_host()
        signal = OrderSignal("Sell", 1, 18000.0, "exit", exchange_ts=1)
        self.assertFalse(host._validate_order_signal(signal))

    def test_accepts_valid_entry(self):
        host = make_host()
        signal = OrderSignal("Buy", 1, 18000.0, "entry", exchange_ts=1)
        self.assertTrue(host._validate_order_signal(signal))

    def test_accepts_valid_exit_with_position(self):
        host = make_host()
        host.position_qty = 1
        host.position_dir = "Long"
        signal = OrderSignal("Sell", 1, 18000.0, "exit", exchange_ts=1)
        self.assertTrue(host._validate_order_signal(signal))


if __name__ == "__main__":
    unittest.main()
