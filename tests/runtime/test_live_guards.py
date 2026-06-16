"""Tests for order error classification and session watchdog."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from trading_engine.core.types import OrderSignal
from trading_engine.order_errors import (
    OrderErrorCategory,
    classify_order_error,
    should_retry_order,
)
from trading_engine.testing.helpers import arm_pending_exit, make_host


class TestOrderErrors(unittest.TestCase):
    def test_classify_retryable_timeout(self):
        self.assertEqual(
            classify_order_error(TimeoutError("connection timed out")),
            OrderErrorCategory.RETRYABLE,
        )

    def test_classify_fatal_balance(self):
        self.assertEqual(
            classify_order_error(RuntimeError("insufficient margin balance")),
            OrderErrorCategory.FATAL,
        )

    def test_exit_retry_policy(self):
        self.assertTrue(
            should_retry_order(
                intent="exit",
                category=OrderErrorCategory.RETRYABLE,
                attempt=0,
                max_retries=3,
            )
        )
        self.assertFalse(
            should_retry_order(
                intent="entry",
                category=OrderErrorCategory.RETRYABLE,
                attempt=0,
                max_retries=3,
            )
        )


class TestLiveGuards(unittest.TestCase):
    def test_entry_failure_clears_pending(self):
        host = make_host()
        host.contract = MagicMock(code="TXFR1")
        host.api.futopt_account = MagicMock()
        host.api.place_order.side_effect = TimeoutError("timeout")
        host.is_pending = True
        host.pending_intent = "entry"

        host.place_order(OrderSignal("Buy", 1, 18000.0, "entry", exchange_ts=100))
        self.assertFalse(host.is_pending)

    def test_exit_failure_keeps_pending_and_schedules_retry(self):
        host = make_host()
        host.contract = MagicMock(code="TXFR1")
        host.api.futopt_account = MagicMock()
        host.api.place_order.side_effect = TimeoutError("timeout")
        arm_pending_exit(host)

        host.place_order(
            OrderSignal("Sell", 1, 18000.0, "exit", exchange_ts=200)
        )
        self.assertTrue(host.is_pending)
        self.assertGreater(host._exit_order_retry_at, 0)

    def test_session_watchdog_triggers_relogin(self):
        host = make_host()
        host._api_connected = False
        host._disconnect_since = host._clock() - 60
        host._session_relogin_attempts = 0
        host._next_relogin_at = 0
        host.contract = MagicMock(code="TXFR1")
        host.api.login = MagicMock()
        host._on_reconnected = MagicMock()

        host._check_session_watchdog()
        host.api.login.assert_called_once()
        host._on_reconnected.assert_called_once()


if __name__ == "__main__":
    unittest.main()
