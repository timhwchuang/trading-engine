# Trading Engine — Design & State Machine

This document defines the **kernel invariants**, state dimensions, and transition expectations for the `trading-engine` futures execution host. It is the source of truth for correctness.

See also: [SPEC.md](../SPEC.md), [README.md](../README.md)

## Goals & Non-Goals

**Kernel owns**:
- Tick ingestion → strategy decision → pending order lifecycle → fill application → position accounting
- Session boundaries and hard safety actions (e.g. force-flatten)
- Risk gates passed to (but not decided by) strategy
- Broker-neutral surface via ports + adapters

**Kernel does NOT own** (by design):
- Strategy decision rules (pluggable via `Strategy` Protocol)
- Persistence, alerts, reporting, backtest replay clock

## State Dimensions (single source of truth)

| Dimension          | Legal values                            | Invariant / Notes                                                    |
| ------------------ | --------------------------------------- | -------------------------------------------------------------------- |
| `position_qty`     | `int >= 0`                              | 0 means Flat. Primary accounting field (Phase 1+).                   |
| `position_dir`     | `"Flat" \| "Long" \| "Short"`           | Must be `"Flat"` exactly when `position_qty == 0`.                   |
| `is_pending`       | `bool`                                  | True while an order (entry or exit) is in flight.                    |
| `pending_intent`   | `"entry" \| "exit" \| None`             | Must be set when `is_pending`.                                       |
| `exit_pending`     | `bool`                                  | Refinement of pending for exits (used for guards).                   |
| `pending_order_id` | `str \| None`                           | Used for strict callback + reconcile matching.                       |
| `filled_qty`       | `int` (accumulated for current pending) | For IOC partial handling; only cleared on full completion or cancel. |

`has_position` is a **derived** `@property` → `position_qty > 0` (prevents drift).

## Key Kernel Invariants (guaranteed by the host)

1. While `is_pending`, no new order will arm: `_validate_order_signal` hard-rejects any signal when pending; strategy should also respect `RiskGate.is_pending`.
2. After `session_force_flatten_time`, if `position_qty > 0` and not already exiting, **the kernel itself** produces an exit `OrderSignal` (Phase 2). Strategy may customize via `session_force_flatten_signal`.
3. `position_qty` is only mutated by:
   - `sync_positions` (from broker list_positions)
   - `_apply_deal_fill` on matching deal for the current pending order (full apply only on complete fill of that pending for first version)
4. Exit is **full flatten** in the current version: `position_qty` goes 0 on successful exit fill.
5. IOC partial fills: `filled_qty < pending_qty` → pending remains; only when `filled_qty >= expected` do we apply the position change and clear pending.
6. Wrong `order_id` or non-pending deal/fill events are ignored with warning log (idempotency / replay safety).
7. Reconnect / timeout reconcile paths use `update_status` + `order_deal_records` fallback and always re-check `_still_own_pending` under lock before mutating.
8. Daily risk (pnl, consecutive_loss, block_new_entry) is reset on `trading_day_for_daily_reset` change (exchange local date).

## Transition Summary (simplified)

```
Flat (qty=0, dir=Flat)
  | entry signal (risk allows) --> PendingEntry (is_pending, intent=entry, qty=signal.qty)
  | force_flatten (qty>0)      --> PendingExit (kernel generated)
  | exit signal                --> PendingExit

PendingEntry
  | deal (order_id match) + filled >= pending --> Long/Short (qty=filled, dir=..., clear pending)
  | cancel / timeout / op fail                --> Flat (clear pending, possible block_new_entry)
  | wrong order_id deal                       --> ignore

PendingExit
  | deal (order_id match) + filled >= pending --> Flat (qty=0, clear pending, record PnL)
  | cancel / timeout                          --> (reconcile); may leave position; block_new_entry on hard failure

Any position
  | sync_positions (reconnect/startup) --> qty/dir/price updated from broker; peak calibration on next tick if resynced
```

See `order_executor.py:_apply_deal_fill`, `_arm_pending`, `session.py:sync_positions`, `engine.py:on_tick` + `_maybe_kernel_force_flatten`.

## Force Flatten Ownership (Phase 2)

- Trigger: kernel in the tick hot path (inside lock, before `process_strategy`).
- `RiskGate.force_flatten` is still computed and passed to strategy for awareness.
- `strategy.session_force_flatten_signal(...)` is the **customization hook only**.
- Default synthesized exit uses `flatten_slippage_points` and current `position_qty`.

## PendingIntent Enum (lightweight)

`core/trading_state.py` defines `PendingIntent(StrEnum)` for documentation and guard helpers. String values `"entry"` / `"exit"` remain the wire format (OrderSignal, config, logs).

`validate_pending_consistency(...)` is called in a few hot paths and only logs warnings on obvious drift (never raises in production).

## Adding a New Broker Adapter

1. Implement `OrderAdapter` (order construction) — see `adapters/shioaji.py` vs `mock.py`.
2. Provide a `BrokerPort` duck (or wrapper).
3. (Recommended) Provide a small live bootstrap + `Tick* -> TickSnapshot` converter in a `xxx_live.py`.
4. Use / contribute `adapters/position_normalizer.py` for any direction fields.
5. Never add `import shioaji` (or other broker) to `engine.py`, `session.py`, `order_executor.py`, `core/*` except under `TYPE_CHECKING` or inside the adapter module.

## Testing Philosophy

- Kernel tests live in this repo and must run with zero broker SDKs installed (`python run_tests.py`).
- Adversarial coverage (duplicate callbacks, reconnect races, qty mismatch, force at boundary while pending, etc.) is mandatory for changes to state machine.
- Strategy plugins are tested against the public `Strategy` Protocol + sample `PositionSnapshot` / `RiskGate` (qty included since Phase 1).

## Versioning Note

PositionSnapshot gained `qty: int = 0` (additive, defaulted). Callers using keyword args are unaffected. Direct construction in external tests should be updated to pass `qty` when asserting non-1-lot behavior.

---

**This design favors explicit invariants + narrow mutation paths over a monolithic StateMachine object (keeps the runtime tiny and backtest-friendly).**

## Position model limitations

This kernel is **not** a general position manager:

- Single direction at a time (`Long` / `Short` / `Flat`)
- Full entry and full exit only (`position_qty` → 0 on exit fill)
- `sync_positions` uses the **first** matching non-zero broker position
- No scale-in, partial exit, or multi-leg netting

Designed for ~1-lot TAIFEX day-session strategies. See [SPEC.md §4.2.1](../SPEC.md) and [LIVE_SAFETY.md](LIVE_SAFETY.md).

## State observation (do not mutate)

`TradingEngine` exposes mutable attributes for kernel simplicity. **External code must not assign to them.** Use `get_state_snapshot()` for read-only telemetry. Direct mutation bypasses invariants and is undefined behavior.

## See also

- [LIVE_SAFETY.md](LIVE_SAFETY.md) — failure scenarios and operator actions
- [STRATEGY.md](STRATEGY.md) — strategy author rules
