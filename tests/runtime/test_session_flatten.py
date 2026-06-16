"""Session flatten time boundaries and signal audit formatting."""

from __future__ import annotations

import datetime
import json
import unittest

from trading_engine.calendar.taifex import is_at_or_after
from trading_engine.core.audit.signal_audit import SignalAudit, format_signal_audit
from trading_engine.testing.defaults import default_test_settings


def _dt(hour: int, minute: int, second: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 6, 10, hour, minute, second)


class TestSessionFlattenTimes(unittest.TestCase):
    def setUp(self) -> None:
        self.s = default_test_settings()

    def test_entry_blocked_from_flatten_time(self):
        self.assertFalse(is_at_or_after(_dt(13, 39, 59), self.s.session_flatten_time))
        self.assertTrue(is_at_or_after(_dt(13, 40, 0), self.s.session_flatten_time))

    def test_force_flatten_from_1344(self):
        self.assertFalse(is_at_or_after(_dt(13, 43, 59), self.s.session_force_flatten_time))
        self.assertTrue(is_at_or_after(_dt(13, 44, 0), self.s.session_force_flatten_time))


class TestSignalAudit(unittest.TestCase):
    def test_format_is_valid_json(self):
        raw = format_signal_audit(
            SignalAudit(
                intent="entry",
                direction="Buy",
                price=18000.0,
                ts=1,
                vol_1s=200,
                buy_ratio=0.85,
                atr=30.0,
                multiplier=2.5,
                vol_threshold=375.0,
                vwap=17995.0,
                reason="pullback",
            )
        )
        parsed = json.loads(raw)
        self.assertEqual(parsed["intent"], "entry")
        self.assertEqual(parsed["vol_threshold"], 375.0)


if __name__ == "__main__":
    unittest.main()
