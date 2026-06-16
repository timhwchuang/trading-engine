"""Skeleton live bootstrap — copy into your app and replace My* placeholders."""

from __future__ import annotations

# import shioaji as sj
# from trading_engine import TradingEngine, RuntimeConfig, Settings
# from trading_engine.adapters.shioaji import ShioajiOrderAdapter
# from trading_engine.adapters.shioaji_live import ShioajiLiveBootstrap


def build_engine():
    """Return a configured TradingEngine for live (after you fill in placeholders)."""
    # settings = Settings(...)  # app: yaml + env
    # cfg = RuntimeConfig(settings)
    # api = sj.Shioaji(simulation=cfg.simulation)
    #
    # return TradingEngine(
    #     api=api,
    #     strategy=MyStrategy(),
    #     runtime_config=cfg,
    #     order_adapter=ShioajiOrderAdapter(api=api),
    #     telemetry=MyTelemetry(),
    #     trend_refresh=MyTrendRefresh(),
    #     alerts=MyAlerts(),
    #     archive=MyArchive(),
    # )
    raise NotImplementedError("Replace My* classes and uncomment wiring in your app")


def main() -> None:
    # engine = build_engine()
    # engine.login()
    # ShioajiLiveBootstrap(engine).start_live()
    # engine.run()
    raise NotImplementedError("Implement in your consuming app")


if __name__ == "__main__":
    main()