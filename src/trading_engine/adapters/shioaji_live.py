"""Shioaji live wiring / bootstrap helpers.

This module is the *only* place that should contain Shioaji-specific live
startup, callback registration, subscribe, and TickFOPv1 -> TickSnapshot
conversion for the hot path.

Core engine (engine.py, session.py, order_executor.py) should not perform
these actions directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trading_engine.core.types import TickSnapshot

if TYPE_CHECKING:
    from shioaji import TickFOPv1

    from trading_engine.engine import TradingEngine


class ShioajiLiveBootstrap:
    """Helper to wire a TradingEngine instance for live Shioaji operation.

    Usage (in app layer):
        bootstrap = ShioajiLiveBootstrap(engine)
        bootstrap.start_live()
    """

    def __init__(self, engine: "TradingEngine") -> None:
        self.engine = engine

    def tick_to_snapshot(self, tick: "TickFOPv1") -> TickSnapshot:
        """Convert Shioaji TickFOPv1 into engine-native TickSnapshot."""
        ts = int(tick.datetime.timestamp())
        price = float(tick.close)
        volume = int(tick.volume)
        tick_type = int(getattr(tick, "tick_type", 0) or 0)
        return TickSnapshot(
            ts=ts,
            price=price,
            volume=volume,
            tick_type=tick_type,
            exchange_dt=tick.datetime,
        )

    def on_tick_from_shioaji(self, tick: "TickFOPv1") -> None:
        """Preferred entry point from live quote callback."""
        self.engine.on_tick(self.tick_to_snapshot(tick))

    def subscribe_tick(self) -> None:
        import shioaji as sj

        if self.engine.contract is not None:
            self.engine.api.subscribe(
                self.engine.contract, quote_type=sj.QuoteType.Tick
            )

    def attach(self) -> None:
        """Register broker-neutral hooks on the engine (resubscribe, etc.)."""
        self.engine._resubscribe_ticks = self.subscribe_tick

    def register_callbacks(self) -> None:
        self.engine.api.set_order_callback(self.engine.handle_order_event)
        self.engine.api.set_event_callback(self.engine.handle_session_event)
        if hasattr(self.engine.api, "set_session_down_callback"):
            self.engine.api.set_session_down_callback(self.engine.handle_session_down)

        @self.engine.api.on_tick_fop_v1()
        def _on_tick(tick: "TickFOPv1"):
            self.on_tick_from_shioaji(tick)

    def wire_live(self) -> None:
        """Attach resubscribe hook and register Shioaji callbacks."""
        self.attach()
        self.register_callbacks()

    def start_live(self) -> None:
        """Full live startup: login, wire callbacks, subscribe ticks, run loop."""
        self.engine.login()
        self.wire_live()
        self.subscribe_tick()
        self.engine.run()


__all__ = ["ShioajiLiveBootstrap"]