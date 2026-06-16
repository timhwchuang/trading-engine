"""Strategy Protocol injection and reset delegation."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock

from trading_engine.adapters.mock import MockOrderAdapter
from trading_engine.core.strategy import BaseStrategy, StrategySideEffects
from trading_engine.engine import TradingEngine
from trading_engine.testing.defaults import default_runtime_config
from trading_engine.testing.helpers import StubStrategy, make_host


class _DummyStrategy(BaseStrategy):
    def evaluate(self, *a, **k):
        return None, StrategySideEffects()

    def reset(self) -> None:
        return None


class TestStrategyInterfaceInjection(unittest.TestCase):
    def test_make_host_accepts_custom_decision_strategy(self):
        dummy = _DummyStrategy()
        host = make_host(decision=dummy)
        self.assertIs(host.strategy, dummy)

    def test_trading_engine_constructor_accepts_strategy(self):
        api = MagicMock()
        dummy = _DummyStrategy()
        host = TradingEngine(
            api=api,
            strategy=dummy,
            runtime_config=default_runtime_config(),
            order_adapter=MockOrderAdapter(api),
        )
        self.assertIs(host.strategy, dummy)

    def test_host_reset_strategy_state_delegates_to_strategy_reset(self):
        calls: list[str] = []

        class _SpyStrategy(_DummyStrategy):
            def reset(self) -> None:
                calls.append("reset")

        api = MagicMock()
        host = TradingEngine(
            api=api,
            strategy=_SpyStrategy(),
            runtime_config=default_runtime_config(),
            order_adapter=MockOrderAdapter(api),
        )
        host.reset_strategy_state()
        self.assertEqual(calls, ["reset"])

    def test_stub_strategy_survives_one_tick(self):
        api = MagicMock()
        dummy = StubStrategy()
        host = TradingEngine(
            api=api,
            strategy=dummy,
            runtime_config=default_runtime_config(),
            order_adapter=MockOrderAdapter(api),
        )
        host._api_connected = True
        host._order_sync_mode = True
        tick = MagicMock()
        tick.datetime = datetime.datetime(2026, 6, 12, 9, 0, 0)
        tick.close = "18000"
        tick.volume = 1
        tick.tick_type = 1
        host.on_tick(tick)


if __name__ == "__main__":
    unittest.main()
