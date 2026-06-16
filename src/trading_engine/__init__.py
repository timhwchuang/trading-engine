"""TradingEngine — broker-agnostic execution host (independent package)."""

from trading_engine._version import __version__
from trading_engine.calendar.port import MarketCalendarPort, TaifexMarketCalendar
from trading_engine.core.runtime_config import RuntimeConfig
from trading_engine.core.strategy import BaseStrategy, Strategy, StrategySideEffects
from trading_engine.core.trading_state import PendingIntent
from trading_engine.core.types import EngineStateSnapshot, TickSnapshot
from trading_engine.engine import TradingEngine
from trading_engine.plugins import ENTRY_POINT_GROUP, load_strategy
from trading_engine.settings import Settings

__version__ = __version__

__all__ = [
    "BaseStrategy",
    "EngineStateSnapshot",
    "ENTRY_POINT_GROUP",
    "MarketCalendarPort",
    "PendingIntent",
    "RuntimeConfig",
    "Settings",
    "Strategy",
    "StrategySideEffects",
    "TaifexMarketCalendar",
    "TickSnapshot",
    "TradingEngine",
    "__version__",
    "load_strategy",
]
