"""Phase 2: Kernel-owned force flatten tests (hard session boundary safety)."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock

from trading_engine.core.strategy import BaseStrategy, StrategySideEffects
from trading_engine.core.types import OrderSignal
from trading_engine.testing.helpers import make_host


def _dt_force() -> datetime.datetime:
    # After session_force_flatten_time (13:44) in default_test_settings
    return datetime.datetime(2026, 6, 10, 13, 44, 30)


class _ForceSpyStrategy(BaseStrategy):
    """Strategy that can return custom force flatten signal or None."""

    def __init__(self):
        self.force_calls = 0
        self.last_market = None
        self.custom_signal: OrderSignal | None = None

    def evaluate(self, *args, **kwargs):
        return None, StrategySideEffects()

    def reset(self) -> None:
        return None

    def session_force_flatten_signal(self, market, position, session_force_flatten_time):
        self.force_calls += 1
        self.last_market = market
        if self.custom_signal is not None:
            return self.custom_signal, StrategySideEffects()
        return None, StrategySideEffects()


class TestKernelForceFlatten(unittest.TestCase):
    def test_stub_strategy_no_signal_kernel_produces_default_exit(self):
        host = make_host()
        host.position_qty = 2
        host.position_dir = "Long"
        host.entry_price = 18000.0
        host.trailing_peak = 18010.0

        sig = host._maybe_kernel_force_flatten(1_700_000_100, 18005.0, _dt_force())

        self.assertIsNotNone(sig)
        self.assertEqual(sig.intent, "exit")
        self.assertEqual(sig.qty, 2)  # full current position
        self.assertIn(sig.action, ("Sell", "Buy"))
        # default uses flatten_slippage_points (8 in test defaults)
        self.assertEqual(sig.slippage_points, host._cfg.flatten_slippage_points)

    def test_custom_strategy_signal_is_used(self):
        spy = _ForceSpyStrategy()
        host = make_host(decision=spy)
        host.position_qty = 1
        host.position_dir = "Short"
        host.entry_price = 18100.0

        custom = OrderSignal(
            "Buy", 1, 18090.0, "exit", exchange_ts=1_700_000_200, slippage_points=5
        )
        spy.custom_signal = custom

        sig = host._maybe_kernel_force_flatten(1_700_000_200, 18095.0, _dt_force())

        self.assertIs(sig, custom)
        self.assertEqual(spy.force_calls, 1)

    def test_no_trigger_when_no_position(self):
        host = make_host()
        host.position_qty = 0
        host.position_dir = "Flat"

        sig = host._maybe_kernel_force_flatten(1_700_000_300, 18000.0, _dt_force())
        self.assertIsNone(sig)

    def test_no_trigger_when_pending(self):
        host = make_host()
        host.position_qty = 1
        host.position_dir = "Long"
        host.is_pending = True
        host.pending_intent = "entry"

        sig = host._maybe_kernel_force_flatten(1_700_000_400, 18000.0, _dt_force())
        self.assertIsNone(sig)

    def test_no_trigger_when_exit_pending(self):
        host = make_host()
        host.position_qty = 1
        host.position_dir = "Long"
        host.exit_pending = True
        host.is_pending = True
        host.pending_intent = "exit"

        sig = host._maybe_kernel_force_flatten(1_700_000_500, 18000.0, _dt_force())
        self.assertIsNone(sig)

    def test_force_signal_arms_as_exit_in_on_tick_flow(self):
        """Integration: on_tick with force time + position should arm exit via kernel signal."""
        host = make_host()
        host._order_sync_mode = True  # direct place in this test (no worker)
        host.contract = MagicMock(code="TXFR1")
        host.api.futopt_account = MagicMock()
        host.position_qty = 1
        host.position_dir = "Long"
        host.entry_price = 18000.0

        tick = MagicMock()
        tick.datetime = _dt_force()
        tick.close = "18010"
        tick.volume = 10
        tick.tick_type = 1

        host.on_tick(tick)

        self.assertTrue(host.is_pending)
        self.assertTrue(host.exit_pending)
        self.assertEqual(host.pending_intent, "exit")
        self.assertEqual(host.pending_qty, 1)


if __name__ == "__main__":
    unittest.main()
