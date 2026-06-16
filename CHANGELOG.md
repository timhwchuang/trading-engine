# Changelog

All notable changes to `trading-engine` are documented here.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versioning follows [SemVer](https://semver.org/) (0.x = API may still evolve).

## [0.2.1] - 2026-06-16

Patch release to support `strategy-vwap-momentum` v0.1.0 (first public reference strategy plugin) and improve sweep integration.

### Added
- `momentum_timeout_sec` (with const `MOMENTUM_TIMEOUT_SEC`) to `Settings`, `SWEEP_FIELD_TO_CONST`, `_CONST_TO_SNAKE`, and test defaults.
  - Enables first-class `patch_strategy_params` / sweep support for the momentum episode timeout in strategy plugins.
  - Default 180s (matching previous hardcoded value in the reference plugin).

### Changed
- `SWEEPABLE_PARAMS` in consuming strategy plugins (e.g. `strategy-vwap-momentum`) will now automatically surface `MOMENTUM_TIMEOUT_SEC`.

## [0.2.0] - 2026-06-16

UAT-ready release addressing [CodeReview#2](CodeReview#2.md) (see [CodeReview#2-re.md](CodeReview#2-re.md) for re-review).

### Added

- `TradingEngine.get_state_snapshot()` and frozen `EngineStateSnapshot` for read-only state observation
- `_validate_order_signal()` — kernel rejects invalid `OrderSignal` before arming pending
- `RuntimeConfig.warn_if_placeholder_credentials()` on live login
- Docs: [docs/LIVE_SAFETY.md](docs/LIVE_SAFETY.md), [docs/STRATEGY.md](docs/STRATEGY.md), [docs/MIGRATION_FROM_THEMAN.md](docs/MIGRATION_FROM_THEMAN.md), [docs/UAT_CHECKLIST.md](docs/UAT_CHECKLIST.md)
- README: Disclaimer, Live Safety, Go-Live Checklist, Secrets, Logging (`configure_root=False`)
- `.env.example`, [examples/minimal_live/](examples/minimal_live/)
- CI `quality` job: ruff lint/format, gradual mypy, explicit no-shioaji guard step
- Tests: `test_state_snapshot.py`, `test_signal_validation.py` (73 kernel tests total)

### Changed

- Logger name `theman` → `trading_engine`; lazy `get_logger()` init
- SPEC.md: CI status, position model scope (§4.2.1), theman section historicalized
- DESIGN.md: position limitations, state observation warnings, pending hard-guard invariant
- Ruff format applied across `src/` and `tests/` (CI enforcement)

### Fixed

- Removed last `theman` reference in `NullTelemetryPort` docstring

## [0.1.0] - 2026-06 (initial public release)

- Broker-agnostic futures execution kernel (Shioaji + Mock adapters)
- `position_qty` model, kernel-owned force-flatten, reconnect reconcile
- 63 kernel tests, GitHub Actions CI matrix (Python 3.11–3.13)
- Core docs: README, SPEC, DESIGN

[0.2.0]: https://github.com/timhwchuang/trading-engine/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/timhwchuang/trading-engine/releases/tag/v0.1.0