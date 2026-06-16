# Backtest Host Contract

> **Owner**: `trading-engine`  
> **Consumers**: `trading-backtest`, kernel tests, any replay driver  
> **App checklist**: [trading-app UAT_CHECKLIST](https://github.com/timhwchuang/trading-app/blob/main/docs/UAT_CHECKLIST.md)

`BacktestEngine` must drive the **same** `TradingEngine` class as live. This document lists the host API surface replay depends on.

---

## Golden rules

1. **Decision logic lives in Strategy plugins** — never in the replay driver.
2. Replay may only **inject**: `api`, `clock`, `strategy`, ports, `order_adapter`, `runtime_config`.
3. No `time.time()` / `datetime.now()` / `date.today()` on the replay path.
4. Lock rule: do not call `refresh_atr()` while holding the engine lock (deadlock). Backtest uses pre-tick sync refresh (see backtest spec §7.1).

---

## Constructor

```python
TradingEngine(
    api,                    # required — MockBroker in backtest
    strategy,               # Strategy plugin
    runtime_config,
    order_adapter,          # explicit MockOrderAdapter or ShioajiOrderAdapter
    clock=None,             # VirtualClock in backtest
    telemetry=...,          # optional ports
)
```

---

## Tick input

`on_tick(tick)` expects duck-typed tick with:

| Field | Type | Notes |
|-------|------|-------|
| `datetime` | `datetime` | Taipei naive |
| `close` | `str` or `float` | Engine normalizes |
| `volume` | `int` | |
| `tick_type` | `int` | |

---

## Order / fill contract

- `place_order(signal)` → `api.place_order(contract, order, timeout=0)` → object with `.order.id`
- `handle_order_event(stat, msg)`:
  - `FuturesDeal`: `price`, `quantity`, `action`, `trade_id`
  - `FuturesOrder` (cancel): `operation`, `status`, `trade_id`

Pending fields used by replay: `pending_order_id`, `pending_intent`, `is_pending`, `pending_qty`, etc.

---

## ATR / kbars

- `refresh_atr()` calls `api.kbars(contract, start, end)` expecting `.High` / `.Low` / `.Close` lists.
- Backtest sets `_maybe_refresh_atr` to no-op; driver refreshes **before** `on_tick` outside lock.

---

## Session / premarket

- `exchange_time.is_trading_session(dt, SESSION_START, SESSION_END)` gates **decision** (`on_tick`).
- Premarket ticks may still run matching + pending timeout (see backtest implementation spec).

---

## Audit lines (determinism)

Kernel + telemetry emit:

- `SIGNAL_AUDIT {json}`
- `FILL_AUDIT {json}`
- `DAILY_SUMMARY {json}`

See `trading-app/docs/AuditContract.md` for field semantics.

---

## Tests (engine repo)

Kernel state machine, pending, session, risk gates — `python run_tests.py` in `trading-engine`.

Integration scenarios — [UAT_CHECKLIST.md](UAT_CHECKLIST.md) Phase B/C.