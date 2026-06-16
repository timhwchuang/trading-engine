"""Phase 6: qty mismatch / over-fill warning paths."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from trading_engine.core.order_events import FUTURES_DEAL
from trading_engine.testing.helpers import arm_pending_entry, make_host


class TestQtyMismatchGuard(unittest.TestCase):
    def test_deal_qty_larger_than_pending_logs_warning_but_applies(self):
        host = make_host()
        arm_pending_entry(host, qty=1)

        with patch("trading_engine.order_executor.logger") as mock_log:
            msg = {
                "price": "18010",
                "quantity": 5,
                "action": "Buy",
                "trade_id": host.pending_order_id,
            }
            host.handle_order_event(FUTURES_DEAL, msg)

            self.assertEqual(host.position_qty, 5)
            warning_text = " ".join(str(call) for call in mock_log.warning.call_args_list)
            self.assertIn("超過 pending", warning_text)


if __name__ == "__main__":
    unittest.main()
