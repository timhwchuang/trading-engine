# Minimal live wiring example

This is a **skeleton** showing how a consuming app assembles `TradingEngine` for Shioaji live. It does not run standalone without your `Settings`, ports, and strategy.

## What you must provide

| Placeholder | Your implementation |
|-------------|---------------------|
| `Settings(...)` | Load from yaml / env in your app |
| `MyStrategy` | `trading_engine.core.strategy.Strategy` |
| `MyTelemetry` | `TelemetryPort` |
| `MyTrendRefresh` | `TrendRefreshPort` |
| `MyAlerts` | `AlertPort` (CRITICAL on disconnect / pending timeout) |
| `MyArchive` | `ArchivePort` (optional) |

## Flow

1. `pip install "trading-engine[shioaji] @ git+..."`
2. Copy repo-root [`.env.example`](../../.env.example) → `.env`
3. Implement ports + strategy in your app repo
4. Wire as in `bootstrap_stub.py`
5. Run simulation before live

See [docs/LIVE_SAFETY.md](../../docs/LIVE_SAFETY.md) and [README § Go-Live Checklist](../../README.md).