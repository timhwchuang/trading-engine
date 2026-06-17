# UAT Checklist (kernel / consuming app integration)

Use when integrating `trading-engine@v0.2.2` for simulation → paper → small live.

**App deployment** (Windows env, tick archive, reporting): [trading-app `docs/UAT_CHECKLIST.md`](https://github.com/timhwchuang/trading-app/blob/main/docs/UAT_CHECKLIST.md) Phase A/B — run **before** Phase B below.

Prerequisites: [README § Go-Live](../README.md), [LIVE_SAFETY.md](LIVE_SAFETY.md), [STRATEGY.md](STRATEGY.md).

---

## Phase A — Repo & config

| # | Item | Pass | Notes / date |
|---|------|:----:|--------------|
| A1 | App pins `trading-engine@v0.2.2` (git tag) | ☐ | |
| A2 | `.env` from `.env.example`; **not** in git | ☐ | |
| A3 | `python run_tests.py` green in trading-engine repo | ☐ | 73 tests |
| A4 | App boots with `ShioajiLiveBootstrap` + injected ports | ☐ | |

---

## Phase B — Simulation (full session)

| # | Scenario | Pass | Expected | Notes / date |
|---|----------|:----:|----------|--------------|
| B1 | Full trading day tick flow | ☐ | Entry/exit signals, fills, `position_qty` correct | |
| B2 | `session_force_flatten_time` with open position | ☐ | Kernel arms exit; position flat after fill | |
| B3 | Disconnect → reconnect (`event_code` 12/13) | ☐ | `_on_reconnected`: reconcile → sync → resubscribe | |
| B4 | Pending timeout (short `pending_timeout_sec` in test cfg) | ☐ | CRITICAL alert; `block_new_entry`; sync runs | |
| B5 | Invalid strategy signal (test `qty=0`) | ☐ | Warning log; **no** arm | |
| B6 | `get_state_snapshot()` matches broker after sync | ☐ | `snap.position_qty` / `dir` consistent | |

---

## Phase C — Paper trade (≥3 sessions)

| # | Item | Pass | Notes / date |
|---|------|:----:|--------------|
| C1 | `SIGNAL_AUDIT` / `FILL_AUDIT` logged every trade | ☐ | |
| C2 | `DAILY_SUMMARY` at day reset | ☐ | |
| C3 | `AlertPort` received test CRITICAL (manual inject OK) | ☐ | |
| C4 | No direct mutation of `engine.*` state in app/telemetry | ☐ | Code review |
| C5 | No manual orders on same contract as kernel | ☐ | |
| C6 | ATR refresh failures only warn; strategy still safe | ☐ | See LIVE_SAFETY |

---

## Phase D — Small live (1 lot, monitored)

| # | Item | Pass | Notes / date |
|---|------|:----:|--------------|
| D1 | Go-Live Checklist (README) all checked | ☐ | |
| D2 | Capital limit documented (max loss acceptable) | ☐ | |
| D3 | On-call / alert channel active during session | ☐ | |
| D4 | End-of-day: kernel flat or documented exception | ☐ | |
| D5 | Post-mortem log archive (ticks, audits, alerts) | ☐ | |

---

## Phase E — Sign-off

| Field | Value |
|-------|-------|
| App / strategy repo | |
| trading-engine tag | v0.2.2 |
| UAT owner | |
| Simulation completed | |
| Paper sessions (count) | |
| Live sessions (count) | |
| Issues found | |
| **UAT result** | ☐ Pass → continue &nbsp; ☐ Fail → fix before live |

---

## Quick reference: log lines to watch

```
SIGNAL_AUDIT
FILL_AUDIT
DAILY_SUMMARY
ALERT [CRITICAL]
拒絕 OrderSignal
Pending 超時
Session 看門狗
No-tick 看門狗
持倉對帳
```

## After UAT

Record outcomes in your app repo (wiki / issue). Open kernel issues only for **reproducible** bugs with test or log evidence.