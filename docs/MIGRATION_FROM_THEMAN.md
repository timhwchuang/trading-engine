# Historical: Migration from theman monorepo

> **For previous internal consumers only.** New users can ignore this document.

This package was extracted from an internal `theman` monorepo. The mapping below is kept for teams that still maintain thin re-export layers in the old repo.

| Original theman path                         | Current trading-engine                    |
| -------------------------------------------- | ----------------------------------------- |
| `src/runtime/engine.py`                      | `engine.py`                               |
| `src/runtime/session.py`                     | `session.py`                              |
| `src/runtime/order_executor.py`              | `order_executor.py`                       |
| `src/core/*` (types, ports, order_events, …) | `core/*`                                  |
| `src/adapters/*`                             | `adapters/*`                              |
| `src/exchange_time.py`                       | `calendar/taifex.py` + `exchange_time.py` |

Legacy theman paths may remain as 2-5 line re-export shims. **Do not** add new dependencies from `trading-engine` back to `theman`.