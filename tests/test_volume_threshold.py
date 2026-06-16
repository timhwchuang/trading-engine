"""P1-2: opening volume ladder and vol_threshold tests."""

from __future__ import annotations

import datetime
import unittest

from trading_engine.calendar.taifex import compute_vol_threshold, opening_session_multiplier
from trading_engine.testing.defaults import default_test_settings


def _dt(hour: int, minute: int, second: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 6, 10, hour, minute, second)


class TestOpeningSessionMultiplier(unittest.TestCase):
    def test_futures_window_includes_085959(self):
        mult = opening_session_multiplier(
            _dt(8, 59, 59),
            mult_futures=2.5,
            mult_spot=1.5,
            mult_normal=1.0,
        )
        self.assertEqual(mult, 2.5)

    def test_spot_window_starts_at_090000(self):
        mult = opening_session_multiplier(
            _dt(9, 0, 0),
            mult_futures=2.5,
            mult_spot=1.5,
            mult_normal=1.0,
        )
        self.assertEqual(mult, 1.5)

    def test_spot_window_includes_091459(self):
        mult = opening_session_multiplier(
            _dt(9, 14, 59),
            mult_futures=2.5,
            mult_spot=1.5,
            mult_normal=1.0,
        )
        self.assertEqual(mult, 1.5)

    def test_normal_from_091500(self):
        mult = opening_session_multiplier(
            _dt(9, 15, 0),
            mult_futures=2.5,
            mult_spot=1.5,
            mult_normal=1.0,
        )
        self.assertEqual(mult, 1.0)

    def test_futures_window_starts_at_084500(self):
        mult = opening_session_multiplier(
            _dt(8, 45, 0),
            mult_futures=2.5,
            mult_spot=1.5,
            mult_normal=1.0,
        )
        self.assertEqual(mult, 2.5)


class TestVolThreshold(unittest.TestCase):
    def setUp(self) -> None:
        self.s = default_test_settings()

    def test_uses_base_vol_floor(self):
        base, mult, threshold = compute_vol_threshold(
            current_atr=10.0,
            dt=_dt(10, 0),
            base_vol=self.s.base_vol,
            atr_vol_mult=self.s.atr_vol_mult,
            mult_futures=self.s.open_mult_futures,
            mult_spot=self.s.open_mult_spot,
            mult_normal=self.s.open_mult_normal,
        )
        self.assertEqual(base, self.s.base_vol)
        self.assertEqual(mult, self.s.open_mult_normal)
        self.assertEqual(threshold, self.s.base_vol * self.s.open_mult_normal)

    def test_atr_raises_base_above_floor(self):
        base, mult, threshold = compute_vol_threshold(
            current_atr=200.0,
            dt=_dt(10, 0),
            base_vol=self.s.base_vol,
            atr_vol_mult=self.s.atr_vol_mult,
            mult_futures=self.s.open_mult_futures,
            mult_spot=self.s.open_mult_spot,
            mult_normal=self.s.open_mult_normal,
        )
        self.assertEqual(base, 200.0)
        self.assertEqual(threshold, 200.0)

    def test_opening_multiplier_scales_threshold(self):
        _, mult, threshold = compute_vol_threshold(
            current_atr=30.0,
            dt=_dt(8, 50),
            base_vol=self.s.base_vol,
            atr_vol_mult=self.s.atr_vol_mult,
            mult_futures=self.s.open_mult_futures,
            mult_spot=self.s.open_mult_spot,
            mult_normal=self.s.open_mult_normal,
        )
        self.assertEqual(mult, self.s.open_mult_futures)
        self.assertEqual(threshold, 150.0 * self.s.open_mult_futures)


if __name__ == "__main__":
    unittest.main()
