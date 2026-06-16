# Strategy Plugin Guide

How to implement and maintain a strategy for `TradingEngine`. Source of truth for the Protocol: [`core/strategy.py`](../src/trading_engine/core/strategy.py).

## Quick start

```python
from trading_engine.core.strategy import BaseStrategy, StrategySideEffects
from trading_engine.core.types import OrderSignal, MarketSnapshot, PositionSnapshot, RiskGate

class MyStrategy(BaseStrategy):
    def evaluate(self, market, position, risk, vol_threshold, **kwargs):
        if risk.is_pending or risk.block_new_entry:
            return None, StrategySideEffects()
        # ... your logic ...
        return OrderSignal("Buy", 1, market.price, "entry", exchange_ts=market.ts), StrategySideEffects()

    def reset(self) -> None:
        # clear episode state after fills / session events
        pass
```

Inject at app layer: `TradingEngine(strategy=MyStrategy(), ...)`.

## Protocol surface

| Method | Required? | Default (`BaseStrategy`) | Purpose |
|--------|-------------|--------------------------|---------|
| `evaluate` | **Yes** | abstract | Main entry/exit decision per tick |
| `reset` | **Yes** (may be no-op) | no-op | Clear intra-episode state |
| `manage_exit` | Optional | `(None, StrategySideEffects())` | Trailing / TP / stop while in position |
| `build_entry_audit` | Optional | minimal `SignalAudit` | Logging / telemetry enrichment |
| `build_exit_audit` | Optional | minimal `SignalAudit` | Logging / telemetry enrichment |
| `session_force_flatten_signal` | Optional | `(None, StrategySideEffects())` | Customize kernel force-flatten exit |

`evaluate` receives a pre-computed [`RiskGate`](../src/trading_engine/core/types.py): use it — do not re-derive session/pending flags independently.

## MUST (strategy authors)

1. **Respect `RiskGate`** — return `None` when `is_pending`, `block_new_entry` (for entries), `api_connected` is false, or session gates forbid action.
2. **Return valid `OrderSignal`** — `qty > 0`, `intent` in `"entry"` / `"exit"`, `action` in `"Buy"` / `"Sell"`. Kernel rejects invalid signals (see [LIVE_SAFETY.md](LIVE_SAFETY.md)).
3. **Match intent to position** — entry only when flat (`position.qty == 0`); exit only when `position.qty > 0`.
4. **Do not mutate `TradingEngine`** — strategy must be pure decision logic; no writing `engine.position_qty`, `engine.is_pending`, etc.
5. **Implement `reset`** — clear momentum / episode counters when host calls after fills or resync.

## MUST NOT

- Import broker SDKs (`shioaji`) inside strategy plugins.
- Import app-layer modules (Telegram, yaml loaders, etc.) — keep plugins testable with `MarketSnapshot` / `RiskGate` fixtures.
- Return entry signals while `risk.is_pending` — kernel also hard-blocks, but double-guard avoids log noise.
- Assume multi-lot scaling or partial exit — kernel uses full `position.qty` on exit (see SPEC § Position Model Scope).

## `evaluate` parameters

| Parameter | Description |
|-----------|-------------|
| `market` | `MarketSnapshot` — price, VWAP, ATR, trend, volume |
| `position` | `PositionSnapshot` — includes `qty` (Phase 1+) |
| `risk` | `RiskGate` — pending, session, daily loss, force_flatten flags |
| `vol_threshold` | `(base, multiplier, threshold)` tuple from calendar |
| `session_force_flatten_time` | exchange-local time for hard flatten boundary |
| `max_daily_loss_points` | daily loss cap (strategy may use for soft stops) |
| `on_daily_loss_block` | callback when strategy triggers daily loss block via side effects |

Returns `(OrderSignal | None, StrategySideEffects)`. Set `effects.block_new_entry = True` to stop new entries for the trading day.

## Force flatten hook

At `session_force_flatten_time`, the **kernel** owns the decision to exit. Your `session_force_flatten_signal` may return a customized exit `OrderSignal` (slippage, audit reason). If you return `None`, kernel synthesizes a full exit using `flatten_slippage_points`.

Custom signal **must** have `intent == "exit"` or kernel ignores it.

## Evolution roadmap (0.x → 1.0)

| Version | Plan |
|---------|------|
| **0.x (now)** | Full Protocol above; audit builders stay for backward compatibility |
| **1.0 target** | Smaller community surface: `evaluate` + `reset` required; audit via optional mixin or telemetry callbacks; `manage_exit` may merge into `evaluate` |

Breaking changes (e.g. removing Protocol methods) will trigger a **major** semver bump per [SPEC.md](../SPEC.md) §9.

## Testing your strategy

Test against the Protocol with kernel types only — no `TradingEngine` required:

```python
market = MarketSnapshot(ts=..., price=..., dt=..., vwap=..., ...)
position = PositionSnapshot(has_position=False, position_dir="Flat", qty=0, ...)
risk = RiskGate(is_pending=False, block_new_entry=False, ...)
signal, effects = strategy.evaluate(market, position, risk, (1.0, 1.0, 1.0), ...)
```

Integration tests with `make_host()` belong in your app repo or a dedicated strategy package.

## See also

- [SPEC.md §4.2](../SPEC.md) — public API summary
- [DESIGN.md](DESIGN.md) — kernel invariants
- [LIVE_SAFETY.md](LIVE_SAFETY.md) — failure modes