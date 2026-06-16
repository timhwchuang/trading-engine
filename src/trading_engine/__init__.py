"""TradingEngine — broker-agnostic execution host (independent package)."""

from trading_engine.calendar.port import MarketCalendarPort, TaifexMarketCalendar
from trading_engine.engine import TradingEngine
from trading_engine.core.runtime_config import RuntimeConfig
from trading_engine.core.strategy import BaseStrategy, Strategy, StrategySideEffects
from trading_engine.plugins import ENTRY_POINT_GROUP, load_strategy
from trading_engine.settings import Settings

__all__ = [
    "BaseStrategy",
    "ENTRY_POINT_GROUP",
    "MarketCalendarPort",
    "RuntimeConfig",
    "Settings",
    "Strategy",
    "StrategySideEffects",
    "TaifexMarketCalendar",
    "TradingEngine",
    "load_strategy",
]