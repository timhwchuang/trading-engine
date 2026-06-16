# trading-engine

Broker-agnostic execution host extracted from [theman](../theman).

## Scope

This package owns the **state machine** only:

- `TradingEngine` — tick processing, pending/fills, session, risk gates
- `core/` — types, ports, runtime config, order events
- `adapters/` — Shioaji / Mock order construction
- `exchange_time`, `order_errors`, `indicators`

It does **not** include strategy logic, storage, alerts, or reporting. Wire those via ports at the app layer (see `theman/src/integrations/`).

## Install (editable, monorepo)

```bash
pip install -e ../trading-engine
```

## Usage

```python
from trading_engine import TradingEngine, RuntimeConfig, Settings
from strategy.vwap_momentum import VWAPMomentumStrategy  # app-specific

cfg = RuntimeConfig(settings)  # Settings loaded from your YAML
engine = TradingEngine(
    api=broker,
    strategy=VWAPMomentumStrategy(),
    runtime_config=cfg,
    telemetry=...,   # TelemetryPort
    trend_refresh=...,  # TrendRefreshPort
)
```

## Tests

Theman runs the full 155-test suite against this package via `theman/run_tests.py` (adds `trading-engine/src` to `sys.path`).