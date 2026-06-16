"""Backward-compatible re-exports; prefer trading_engine.calendar.taifex.

DEPRECATED (standalone hygiene):
    New code should import directly from `trading_engine.calendar.taifex`
    or use the `MarketCalendarPort` / `TaifexMarketCalendar` abstractions.
    This module will eventually be removed.
"""

import warnings as _warnings

from trading_engine.calendar.taifex import *  # noqa: F403

_warnings.warn(
    "trading_engine.exchange_time is deprecated. "
    "Use trading_engine.calendar.taifex (or the calendar port) instead.",
    DeprecationWarning,
    stacklevel=2,
)
