# trading-engine

**永豐 Shioaji 台指期執行 kernel** — tick → 策略信號 → 下單 → 成交 → 持倉口數 → session / 風控邊界。

本專案**只支援永豐證券 [Shioaji](https://sinotrade.github.io/)** 作為 live 券商；日盤時段與 calendar 以 **TAIFEX 台指期** 為前提。  
核心狀態機刻意與 SDK 解耦（方便 Mock 測試），**不是**多券商通用產品，也不打算接第二家 broker。

不含策略 alpha、資料存檔、Telegram、報表 — 這些在 app / strategy repo 組裝。

| 文件 | 用途 |
|------|------|
| [SPEC.md](SPEC.md) | 模組邊界、依賴方向、公開 API |
| [docs/DESIGN.md](docs/DESIGN.md) | 狀態維度、不變量、transition 規則 |

## Status

**0.x 實驗期** — API 可能調整。Kernel 不變量（pending 期間不重複 entry、kernel 擁有 force-flatten、`position_qty` 由 sync+fill 維護、錯誤 order_id 忽略等）有測試覆蓋。

**Live 實盤風險自負** — 本 repo 提供執行狀態機，不保證獲利或零故障；請先在 simulation 驗證。

## 支援範圍

| 支援 | 不支援 |
|------|--------|
| 永豐 Shioaji live（`ShioajiLiveBootstrap`） | 元大、群益、IB 等其他券商 |
| 台指期日盤 session / calendar | 夜盤、外盤、現股 |
| Mock broker 回測 / kernel 單測 | 內建 tick replay 框架 |
| IOC limit 單、持倉 sync、重連對帳 | 多帳號、多商品同時交易 |

## Install（GitHub only，不上 PyPI）

### 從 GitHub 安裝（給其他 repo 依賴用）

```bash
# 最新 main
pip install git+https://github.com/<你的帳號>/trading-engine.git

# 鎖定 tag（建議發版時打 git tag）
pip install git+https://github.com/<你的帳號>/trading-engine.git@v0.1.0

# Live 需要 Shioaji SDK
pip install "trading-engine[shioaji] @ git+https://github.com/<你的帳號>/trading-engine.git@v0.1.0"
```

在 consuming repo 的 `pyproject.toml`：

```toml
dependencies = [
  "trading-engine @ git+https://github.com/<你的帳號>/trading-engine.git@v0.1.0",
]
```

### 本地開發

```bash
git clone https://github.com/<你的帳號>/trading-engine.git
cd trading-engine

pip install -e .              # 核心（跑 kernel tests 不需 shioaji）
pip install -e ".[shioaji]"   # + 永豐 Shioaji（live）
```

## Architecture

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Kernel | `engine.py`, `session.py`, `order_executor.py` | 狀態機；核心路徑無 runtime `import shioaji` |
| Types | `core/types.py` | `TickSnapshot`, `PositionSnapshot`, `OrderSignal`, `RiskGate` |
| Live（永豐） | `adapters/shioaji_live.py` | Callback、subscribe、`TickFOPv1` → `TickSnapshot`、重連重訂閱 |
| Orders | `adapters/shioaji.py` / `mock.py` | Shioaji IOC 建單 / Mock 建單 |

`TradingEngine` 的 `api` **必填** — live 時由 app 層建立 `sj.Shioaji(...)` 後注入。

## Usage

### 1. Live（永豐 Shioaji）

需先向永豐申請 API key、CA 憑證；設定由 app 層載入（見 `Settings` / `RuntimeConfig`）。

```python
import shioaji as sj
from trading_engine import TradingEngine, RuntimeConfig, Settings
from trading_engine.adapters.shioaji import ShioajiOrderAdapter
from trading_engine.adapters.shioaji_live import ShioajiLiveBootstrap

settings = Settings(...)  # app 層從 yaml / env 載入
cfg = RuntimeConfig(settings)
api = sj.Shioaji(simulation=cfg.simulation)

engine = TradingEngine(
    api=api,
    strategy=MyStrategy(),
    runtime_config=cfg,
    order_adapter=ShioajiOrderAdapter(api=api),
    telemetry=MyTelemetry(),
    trend_refresh=MyTrendRefresh(),
    alerts=MyAlerts(),
    archive=MyArchive(),
)

ShioajiLiveBootstrap(engine).start_live()
# 等同 engine.start()（內部委派 bootstrap）
```

### 2. Backtest / Replay（Mock）

```python
from trading_engine.core.types import TickSnapshot

engine.on_tick(TickSnapshot(
    ts=..., price=..., volume=..., tick_type=1, exchange_dt=...
))
```

回測時鐘、tick 來源由 `trading-backtest` 或你的 app 負責。

### 3. Kernel Tests（不需安裝 shioaji）

```python
from trading_engine.testing.helpers import make_host, arm_pending_entry
from trading_engine.core.order_events import FUTURES_DEAL

host = make_host()
arm_pending_entry(host, qty=2)
host.handle_order_event(FUTURES_DEAL, {
    "price": "18010", "quantity": 2, "action": "Buy", "trade_id": "o1",
})
assert host.position_qty == 2
```

## Key Guarantees

見 [docs/DESIGN.md](docs/DESIGN.md)。摘要：

- `is_pending` 期間不會 arm 第二筆 entry
- `session_force_flatten_time` 後由 **kernel** 產生 exit（strategy 僅可客製 signal）
- `position_qty` 為持倉事實來源；`sync_positions` + 成交回報維護
- 非當前 `order_id` 的 callback 忽略
- 日內風控計數依交易所交易日重置

## Testing

```bash
python run_tests.py
```

**63** kernel tests（qty、adversarial callbacks、reconnect、sync、force-flatten、core 無 shioaji import）。  
整合測（策略 + live smoke）在 consuming app repo。

## Version

```python
import trading_engine
print(trading_engine.__version__)  # 0.1.0
```

## Extending

- **策略**：實作 `trading_engine.core.strategy.Strategy` Protocol，在 app 注入 `TradingEngine(strategy=...)`
- **副作用**：Telemetry / Archive / Alerts 用 port 注入，不寫進 kernel
- **不計畫**：新增其他券商 adapter；若要 fork 請自行維護

改狀態機路徑前請先讀 [docs/DESIGN.md](docs/DESIGN.md)。

## License

MIT — see [LICENSE](LICENSE).