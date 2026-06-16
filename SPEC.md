# Trading Repo Spec

> **Trading = `trading-engine`**  
> Repo: [`trading-engine`](../trading-engine/) · Package: `trading-engine` · Import: `trading_engine`

## 1. 定位

Broker-agnostic **期貨執行宿主**：單一狀態機，負責 tick → 策略決策 → pending order → fill → session/risk，與券商 API 解耦。

**一句話**：把「怎麼穩健地下單、管倉、管 session」做好；不管「用什麼策略賺錢」。

## 2. In Scope

| 模組 | 職責 |
|------|------|
| `TradingEngine` | 主狀態機：`on_tick`、pending/timeout、fills、daily summary |
| `OrderExecutorMixin` | IOC limit 下單、order queue、callback 處理 |
| `SessionMixin` | session 開閉、force flatten、position sync |
| `core/types.py` | `MarketSnapshot`、`OrderSignal`、`PositionSnapshot`、`RiskGate` 等 |
| `core/ports.py` | `BrokerPort` — engine 對 `api` 的需求契約 |
| `core/strategy.py` | **`Strategy` Protocol**（plugin 公開契約，source of truth） |
| `core/side_effect_ports.py` | `TelemetryPort`、`TrendRefreshPort`、`ArchivePort` 等 |
| `core/order_events.py` | 訂單事件字串常數（live/mock 共用） |
| `core/runtime_config.py` | 引擎 runtime 設定（不含 app yaml 載入） |
| `adapters/` | `ShioajiOrderAdapter`、`MockOrderAdapter` |
| `calendar/` | TAIFEX 交易日曆、`MarketCalendarPort` |
| `exchange_time.py` | 交易時段判斷（re-export calendar） |
| `indicators.py` | 引擎層共用指標 helper（ATR 等，非策略邏輯） |
| `order_errors.py` | 下單錯誤分類 |
| `logging_setup.py` | async logging 設定 |
| `settings.py` | 設定 dataclass（由 app 載入 yaml 後注入） |

## 3. Out of Scope

| 不屬於 Trading | 歸屬 |
|----------------|------|
| 策略邏輯（VWAP、momentum、trend veto） | Strategy plugin |
| Tick replay、Mock 撮合、VirtualClock | Backtest |
| Tick/kbar 存檔、資料 loader | App / Backtest |
| Telegram alert、UAT report | App |
| Param sweep、績效報表 | App |
| Live CLI 入口 | App（theman `live/`） |

## 4. 公開 API（穩定面）

### 4.1 建構

```python
from trading_engine import TradingEngine, RuntimeConfig, Settings
from trading_engine.adapters.shioaji import ShioajiOrderAdapter
from trading_engine.adapters.mock import MockOrderAdapter

engine = TradingEngine(
    api=broker,                    # BrokerPort duck type
    strategy=strategy_instance,    # Strategy Protocol
    runtime_config=cfg,
    order_adapter=ShioajiOrderAdapter(),  # 必須顯式注入（無 api 啟發式）
    telemetry=...,                 # optional TelemetryPort
    trend_refresh=...,           # optional TrendRefreshPort
    clock=...,                     # optional（backtest 注入 VirtualClock）
)
```

### 4.2 Strategy Protocol（給 plugin 實作）

定義於 `trading_engine.core.strategy`：

- `evaluate(...) -> (OrderSignal | None, StrategySideEffects)`
- `reset()`、`manage_exit(...)`、`build_*_audit(...)` 等

**演進方向**（見 strategy spec）：收斂成更小的 community-facing surface；VWAP/momentum 專用方法移出 Protocol 或改 optional mixin。

### 4.3 BrokerPort

文件化 `self.api` 所需方法；runtime 不強制 isinstance，允許 `MockBroker` / `MagicMock`。

### 4.4 Optional extras

```toml
pip install trading-engine           # 核心，無券商依賴
pip install trading-engine[shioaji]  # 永豐 Shioaji adapter
```

## 5. 依賴

| 方向 | 規則 |
|------|------|
| → Strategy | **禁止** import 任何 strategy plugin |
| → Backtest | **禁止** |
| → theman | **禁止** |
| ← Strategy plugin | 只 import `trading_engine.core.*` |
| ← Backtest | import `TradingEngine`、types、adapters |
| ← App | 組裝 engine + ports + strategy |

**Runtime dependencies**：核心 `dependencies = []`；Shioaji 僅在 `[shioaji]` extra。

## 6. 目錄結構（現況 = 目標）

```
trading-engine/
├── SPEC.md
├── README.md
├── pyproject.toml
└── src/trading_engine/
    ├── engine.py
    ├── session.py
    ├── order_executor.py
    ├── adapters/
    ├── calendar/
    ├── core/
    └── ...
```

## 7. 從 theman 遷移對照（已完成）

| 原 theman | 現 trading-engine |
|-----------|-------------------|
| `src/runtime/engine.py` | `engine.py` |
| `src/runtime/session.py` | `session.py` |
| `src/runtime/order_executor.py` | `order_executor.py` |
| `src/core/*`（types, ports, order_events, …） | `core/*` |
| `src/adapters/*` | `adapters/*` |
| `src/exchange_time.py` | `calendar/taifex.py` + `exchange_time.py` |

theman 對應路徑改為 **re-export 薄層**（2–5 行）。

## 8. 測試

| 階段 | 做法 |
|------|------|
| **現在** | 各 repo 自有 test suite（37 + 15 + 27）；theman 79 整合測 |
| **CI** | `scripts/run-all-tests.sh` 或各 repo `run_tests.py` |

Kernel tests 應能在 **不裝 Shioaji、不裝 strategy plugin** 下跑完。

## 9. 版本策略

- **0.x**：Protocol / types 可能調整；與 theman 同步發版
- **1.0**：Strategy Protocol 穩定、semver 保證、獨立 CI 綠燈

Breaking change 範例：`Strategy.evaluate` 簽名變更、`OrderSignal` 欄位移除 → **major bump**。

## 10. 待辦（Trading repo）

- [ ] 自有 kernel test suite + CI
- [ ] `session.sync_positions` 的 `sj.Action.Buy` 改字串化（與 order_events 一致）
- [ ] Strategy Protocol 收斂（community v1）
- [ ] 發布 PyPI（或 GitHub Packages）
- [ ] theman vendored copy → pip / submodule 依賴

## 11. 非目標

- 不做策略 marketplace 宿主（屬 App 或獨立 tooling）
- 不做分散式 order routing / MQ 熱路徑
- 不做多券商抽象層（除 Shioaji + Mock 外，新券商用新 adapter PR）
