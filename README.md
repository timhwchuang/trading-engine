# trading-engine

**永豐 Shioaji 台指期執行 kernel** — tick → 策略信號 → 下單 → 成交 → 持倉口數 → session / 風控邊界。

本專案**只支援永豐證券 [Shioaji](https://sinotrade.github.io/)** 作為 live 券商；日盤時段與 calendar 以 **TAIFEX 台指期** 為前提。  
核心狀態機刻意與 SDK 解耦（方便 Mock 測試），**不是**多券商通用產品，也不打算接第二家 broker。

不含策略 alpha、資料存檔、Telegram、報表 — 這些在 app / strategy repo 組裝。

| 文件 | 用途 |
|------|------|
| [SPEC.md](SPEC.md) | 模組邊界、依賴方向、公開 API |
| [docs/DESIGN.md](docs/DESIGN.md) | 狀態維度、不變量、transition 規則 |
| [docs/STRATEGY.md](docs/STRATEGY.md) | Strategy Protocol、MUST/MUST NOT |
| [docs/LIVE_SAFETY.md](docs/LIVE_SAFETY.md) | 實盤失敗情境與 kernel 行為 |
| [docs/UAT_CHECKLIST.md](docs/UAT_CHECKLIST.md) | Consuming app 整合 UAT 驗收表 |
| [CHANGELOG.md](CHANGELOG.md) | 版本變更紀錄 |

## Disclaimer

**本專案為作者個人研究與學習用途而公開，部分程式與文件在開發過程中借助 AI 協作撰寫與整理。**

本 repo 僅提供期貨執行狀態機的技術實作參考，**不構成**投資建議、交易邀約或獲利保證，作者亦無意提供商業級交易服務。

若你將本專案用於模擬交易以外的**實盤操作**，所有決策、參數設定、資金配置，以及因此產生的盈虧、漏單、斷線或其他損失，**均由使用者自行承擔**。作者與貢獻者不對任何直接或間接損害負責。

使用前請自行評估風險，並遵守當地法規與券商條款。

> **上實盤前必讀**  
> 1. 完整閱讀 [docs/LIVE_SAFETY.md](docs/LIVE_SAFETY.md) 並執行 [docs/UAT_CHECKLIST.md](docs/UAT_CHECKLIST.md)（consuming app 整合驗收）  
> 2. **一律使用 `get_state_snapshot()` 觀察狀態** — 切勿直接修改 `TradingEngine` 的 `position_qty`、`is_pending`、`pending_*` 等屬性  

## Status

**0.x 實驗期** — API 可能調整。Kernel 不變量（pending 期間不重複 entry、kernel 擁有 force-flatten、`position_qty` 由 sync+fill 維護、錯誤 order_id 忽略等）有測試覆蓋。

## Live Trading Safety & Known Limitations

- **Position 模型**：單一方向、全倉進出；`sync_positions` 只取第一筆匹配的非零部位。設計目標是 ~1 口台指日盤策略，**不是**通用部位管理（scale-in、減碼留倉、多商品組合均不支援）。詳見 [SPEC.md §4.2.1](SPEC.md)。
- **狀態觀察**：使用 `engine.get_state_snapshot()` 唯讀觀察。**切勿**直接修改 `TradingEngine` 的 `position_qty`、`is_pending`、`pending_*`、`daily_pnl`、`block_new_entry` 等屬性 — 外部寫入可能破壞狀態機。
- **失敗模式**：斷線、pending 超時、CA 失敗、重登入耗盡等情境的行為與後果見 [docs/LIVE_SAFETY.md](docs/LIVE_SAFETY.md)。

## Go-Live Checklist

上實盤前建議逐項確認：

- [ ] 已在 **simulation / paper trade** 跑過完整交易日
- [ ] API key、CA 憑證放在 `.env`，**未** commit 至 git（見 [.env.example](.env.example)）
- [ ] `AlertPort` 可送 **CRITICAL** 通知（斷線、pending 超時、重登入失敗）
- [ ] 手動演練：斷線重連、`sync_positions`、session 末 force-flatten
- [ ] 小口資金；監控 `SIGNAL_AUDIT` / `FILL_AUDIT` / `DAILY_SUMMARY` log
- [ ] 確認 `block_new_entry` 觸發後策略不再進場
- [ ] 策略回傳的 `OrderSignal` 通過 kernel 驗證（`qty > 0`、合法 intent/action）
- [ ] 不在 kernel 管理的同一合約上手動下單
- [ ] 已完成 [docs/UAT_CHECKLIST.md](docs/UAT_CHECKLIST.md) Phase A–D

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
pip install git+https://github.com/timhwchuang/trading-engine.git

# 鎖定 tag（建議發版時打 git tag）
pip install git+https://github.com/timhwchuang/trading-engine.git@v0.2.2

# Live 需要 Shioaji SDK
pip install "trading-engine[shioaji] @ git+https://github.com/timhwchuang/trading-engine.git@v0.2.2"
```

在 consuming repo 的 `pyproject.toml`：

```toml
dependencies = [
  "trading-engine @ git+https://github.com/timhwchuang/trading-engine.git@v0.2.2",
]
```

### 本地開發

```bash
git clone https://github.com/timhwchuang/trading-engine.git
cd trading-engine

pip install -e .              # 核心（跑 kernel tests 不需 shioaji）
pip install -e ".[shioaji]"   # + 永豐 Shioaji（live）
```

## Architecture

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Kernel | `engine.py`, `session.py`, `order_executor.py` | 狀態機；核心路徑無 runtime `import shioaji` |
| Types | `core/types.py` | `TickSnapshot`, `PositionSnapshot`, `OrderSignal`, `RiskGate`, `EngineStateSnapshot` |
| State | `get_state_snapshot()` | 唯讀觀察；勿直接 mutate engine 屬性 |
| Position | `position_qty` | 單方向、全倉進出（見 SPEC §4.2.1） |
| Live（永豐） | `adapters/shioaji_live.py` | Callback、subscribe、`TickFOPv1` → `TickSnapshot`、重連重訂閱 |
| Orders | `adapters/shioaji.py` / `mock.py` | Shioaji IOC 建單 / Mock 建單 |

`TradingEngine` 的 `api` **必填** — live 時由 app 層建立 `sj.Shioaji(...)` 後注入。

## Usage

### 1. Live（永豐 Shioaji）

需先向永豐申請 API key、CA 憑證；設定由 app 層載入（見 `Settings` / `RuntimeConfig`）。最小範例見 [examples/minimal_live/](examples/minimal_live/)。

### Secrets

```bash
cp .env.example .env
# 編輯 .env — 切勿 commit
```

| 變數 | 用途 |
|------|------|
| `SJ_API_KEY` | 永豐 API key |
| `SJ_SEC_KEY` | 永豐 secret |
| `SJ_CA_PATH` | CA 憑證路徑（live） |
| `SJ_CA_PASSWD` | CA 密碼（live） |
| `SJ_CA_PERSON_ID` | CA 啟用備援 person_id（選填） |

### Logging（consuming app 已有設定時）

`trading_engine` 預設在首次 `get_logger()` 時呼叫 `setup_async_logging()`，會清空 **root** logger 的 handlers。若你的 app 已在 import engine 前配置好 logging，請在 import 前改為：

```python
from trading_engine.logging_setup import setup_async_logging
setup_async_logging(configure_root=False)  # 只設定 trading_engine logger，不動 root
```

### Live wiring

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

**73** kernel tests（qty、adversarial callbacks、reconnect、sync、force-flatten、signal validation、state snapshot、core 無 shioaji import）。  
整合測（策略 + live smoke）在 consuming app repo。  
CI：push / PR 至 `main` 時自動跑 `python run_tests.py`（Python 3.11–3.13）。

## Version

```python
import trading_engine
print(trading_engine.__version__)  # 0.2.2
```

## Observing engine state

```python
snap = engine.get_state_snapshot()
print(snap.position_qty, snap.is_pending, snap.block_new_entry)
# snap is frozen — do not mutate engine fields directly
```

## Extending

- **策略**：實作 `trading_engine.core.strategy.Strategy` Protocol（見 [docs/STRATEGY.md](docs/STRATEGY.md)），在 app 注入 `TradingEngine(strategy=...)`
- **副作用**：Telemetry / Archive / Alerts 用 port 注入，不寫進 kernel
- **不計畫**：新增其他券商 adapter；若要 fork 請自行維護

改狀態機路徑前請先讀 [docs/DESIGN.md](docs/DESIGN.md)。

## License

MIT — see [LICENSE](LICENSE).