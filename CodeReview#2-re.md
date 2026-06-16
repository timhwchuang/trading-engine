# Re-review: CodeReview#2.md 後續修復檢視

**日期**：2026-06-16  
**Reviewer**：Grok (基於完整 codebase 檢視)  
**範圍**：針對 CodeReview#2.md 所列建議，於使用者完成一輪修復後進行 re-review。

## 執行摘要

已完整重新審視整個專案，包含：
- README.md、SPEC.md、docs/DESIGN.md、docs/LIVE_SAFETY.md、docs/STRATEGY.md、docs/MIGRATION_FROM_THEMAN.md
- pyproject.toml、.github/workflows/tests.yml
- 所有核心原始碼（engine.py、session.py、order_executor.py、core/*、adapters/*）
- 73 個 kernel tests（含新增 test_state_snapshot.py、test_signal_validation.py）
- examples/minimal_live/、.env.example
- 執行 `python3 run_tests.py`（全數通過）
- 靜態確認 no-shioaji core import guard

**結論**：本輪修復對 CodeReview#2 所指出的**高優先風險項目（特別是 1–4）** 處理非常對症且徹底。文件質量與防誤用護航大幅提升，已從「對公開開源實盤仍有明顯風險」進化到「對認真閱讀文件的使用者而言，風險透明、邊界清楚、可接受進入 UAT」的 0.x 階段。

核心不變量（pending 期間不重複 entry、kernel 擁有 force-flatten、`position_qty` 由 sync+fill 維護、錯誤 order_id 忽略、reconnect 對帳 hygiene、signal validation）皆有實作 + 測試 + 文件覆蓋。

## 1. 原 CodeReview#2 建議對應修復狀況

### 已完整或大幅解決的項目

#### 1.1 README.md / SPEC.md 過時資訊與 theman baggage（原點 1、7）
- **SPEC.md**：
  - 第 10 節「待辦」：CI pipeline、lint/typecheck、Live safety docs + state snapshot + signal validation guards 皆已標 `[x]`。
  - 第 7 節「歷史遷移」已改為指向獨立文件 `docs/MIGRATION_FROM_THEMAN.md`，並明確標註 **（**Historical — 新使用者可忽略**）**。
  - 新增 §4.2.1「Position Model Scope（重要限制）」，以表格清楚列出支援/不支援項目，並強調「外部整合者請勿假設本 repo 提供一般券商部位管理能力」。
- **README.md**：
  - 新增醒目「**Live Trading Safety & Known Limitations**」專節。
  - 新增「**Go-Live Checklist**」含 8 項 checkbox（paper trade、.env 未 commit、AlertPort CRITICAL、斷線演練、小口資金、監控 audit log、block_new_entry 確認、策略 signal 驗證、不在 kernel 管理合約上手動下單）。
  - Architecture 表更新，加入 `get_state_snapshot()` 與 position 模型限制說明。
  - 專門章節「Observing engine state」展示 snapshot 使用方式 + 警告。
  - 明確引用 `docs/LIVE_SAFETY.md` 與 examples/minimal_live/。
- **docs/MIGRATION_FROM_THEMAN.md** 獨立存在，開頭即說明「For previous internal consumers only. New users can ignore this document.」

#### 1.2 狀態封裝極弱（原點 1，高風險）
- 新增 `TradingEngine.get_state_snapshot() -> EngineStateSnapshot`（`src/trading_engine/engine.py:225`）。
- `EngineStateSnapshot` 定義為 `@dataclass(frozen=True)`（`src/trading_engine/core/types.py:73`）。
- **多層文件護航**（已達「outsider 看完不會誤解」的程度）：
  - README 多處 **切勿直接修改** `position_qty`、`is_pending` 等屬性。
  - DESIGN.md 新增「State observation (do not mutate)」專節，明確說明「Direct mutation bypasses invariants and is undefined behavior.」。
  - LIVE_SAFETY.md 單獨情境「Direct mutation of engine state」：Kernel behavior 為「No protection」，Expected outcome 為「Undefined behavior」。
  - STRATEGY.md MUST NOT 條款：「Do not mutate `TradingEngine`」。
  - `get_state_snapshot()` docstring 內建警告。
- 新增專屬測試 `tests/runtime/test_state_snapshot.py`（驗證欄位一致性、frozen 不可 mutate、pending 狀態反映）。
- **現實評估**：屬性仍維持 public（0.x 設計選擇，維持 hot path 與 backtest 相容性）。無法 100% 防止外部 mutate，但契約已透過文件 + snapshot 建立。風險已從「無警告」降為「有明確 UB 定義 + 強力文件」。

#### 1.3 Position 模型限制文件化（原點 2）
- 多處一致說明：
  - SPEC.md §4.2.1 詳細表格（單一方向、全倉進出、sync 只取第一筆、~1 口台指日盤專用、不支援 scale-in / partial exit / 多商品組合）。
  - README「Position 模型」條款直接連結 SPEC。
  - DESIGN.md「Position model limitations」章節。
  - LIVE_SAFETY.md 也有相關情境。
- `PositionSnapshot` 包含 `qty: int = 0`。

#### 1.4 文件對實盤失敗模式的說明（原點 3）
- **全新文件** `docs/LIVE_SAFETY.md`（品質極高）：
  - 以表格形式涵蓋 review 提及之關鍵情境：
    - Session-end disconnect with open position（13:43）
    - Pending timeout + reconcile failure
    - CA / certificate activation failure
    - Repeated re-login exhaustion
    - No-tick watchdog → resubscribe failure
    - ATR / trend refresh persistent failure
    - Multiple open positions on same contract
    - Reconnect: `trailing_peak` calibration delayed
    - Invalid strategy `OrderSignal`
    - Direct mutation of engine state
  - 每項包含：Kernel behavior、Expected outcome、Operator action + 對應程式碼路徑。
  - 附 reconnect sequence mermaid 圖。
  - 結尾連結 Go-Live Checklist 與其他文件。
- README 與 DESIGN.md 皆明確引用此文件。

#### 1.5 韌性與防呆 + Strategy 回傳驗證（原點 4、5）
- `order_executor.py:19` `_validate_order_signal` 實作完整防護：
  - qty <= 0、非法 intent/action、is_pending、block_new_entry 時 entry、有持倉時 entry、無持倉時 exit 皆 reject 並記 warning。
  - 於 `engine.py:337` `on_tick` lock 內、`_arm_pending` **之前** 執行。
- 新增專屬測試 `tests/runtime/test_signal_validation.py`（涵蓋所有 bad case + 正向案例）。
- 已在 LIVE_SAFETY.md 與 STRATEGY.md 文件化「kernel 會拒絕，策略作者需負責修正」。
- Strategy Protocol 仍維持 evaluate + reset 必實作 + 4 個 optional 方法（manage_exit、build_*_audit、session_force_flatten_signal），BaseStrategy 提供合理 default。
- `docs/STRATEGY.md` 完整說明 Protocol surface、MUST/MUST NOT、evolution roadmap（0.x → 1.0 收斂）、以及如何用純 kernel types 測試 strategy。

#### 1.6 CI 與公開開源 hygiene（原點 6）
- `.github/workflows/tests.yml` 新增 `quality` job：
  - `ruff check src tests`
  - `ruff format --check src tests`
  - `mypy`（針對核心型別檔，non-blocking）
- Test job 明確先執行 `test_no_shioaji_core_import` 再跑 `run_tests.py`（Python 3.11–3.13 matrix）。
- SPEC.md 第 8 節已更新描述 CI 內容。
- `test_no_shioaji_core_import.py` 持續強制（靜態掃描 + 動態 block + 實際 kernel 行為驗證）。
- 新增 `examples/minimal_live/`（含 README 與 bootstrap_stub.py 骨架），降低新手門檻。
- `.env.example` 存在且說明清楚；`RuntimeConfig` 內建 `warn_if_placeholder_credentials` 並在 live 登入時警告。
- Logger 名稱已修正為 `"trading_engine"`（`src/trading_engine/logging_setup.py:14` `LOGGER_NAME`）。

#### 1.7 測試覆蓋
- 實測 `python3 run_tests.py`：**73 tests OK (0.048s)**。
- 新增測試涵蓋 state snapshot、signal validation。
- 既有 adversarial 測試（reconnect race、qty mismatch、force flatten at boundary、duplicate deal、wrong order id 等）持續保留。
- 無需 shioaji 即可完整執行。

### 仍存在、需持續注意的項目（更新後排序）

1. **狀態封裝本質仍弱（中高風險，緩解而非根除）**  
   所有公開屬性（`position_qty`、`is_pending`、`pending_*`、`daily_pnl`、`block_new_entry` 等）仍可從外部任意 mutate。snapshot 為唯讀觀察途徑，但無法阻擋 telemetry、錯誤 strategy 或 app 層直接寫入。  
   **現況**：文件護航已非常充分（多處「undefined behavior」宣告）。對 0.x 階段而言是可接受的取捨（維持簡潔與相容性）。公開使用時仍應在 README 置頂強烈警告。

2. **logging root handler 副作用（次要 hygiene）**  
   `setup_async_logging(configure_root=True)`（預設行為）仍會執行 `root.handlers.clear()`（`logging_setup.py:45`）。若 consuming app 在 engine 啟動前已有 logging 配置，可能被影響。  
   已有 escape hatch `configure_root=False`，但未在主要 README / 使用文件 prominently 說明。屬可改善但不阻礙實盤的項目。

3. **ATR / trend refresh 韌性（已充分文件化）**  
   daemon thread + 失敗僅 warning，無 circuit breaker 或 stale flag 暴露給 strategy。LIVE_SAFETY.md 已明確記載此行為與 operator 應對方式，並註記未來可能加入 `_atr_stale`。與原 review 描述一致，未進一步改動。

4. **Strategy Protocol surface 仍較大（已文件化演進路徑）**  
   維持 6 個方法。`docs/STRATEGY.md` 與 SPEC 皆有 0.x → 1.0 收斂規劃（`evaluate` + `reset` 為主要 required，其餘改 optional mixin 或 telemetry 回呼）。目前對第三方作者仍是負擔，但誤用風險已透過 validation + 文件大幅降低。

5. **其他次要（原 review 點 7）**
   - 同 contract 多筆不同方向持倉：`sync_positions` 仍只取第一筆匹配非零部位 + warning。LIVE_SAFETY.md 有專條說明。
   - `trailing_peak` 重連後校準仍依賴首個 tick，LIVE_SAFETY 已描述「one-tick window of suboptimal peak」。
   - `src/trading_engine/core/side_effect_ports.py:76` 內唯一殘留 "theman" 字樣僅出現在 NullTelemetryPort 的 docstring（"without theman observability"），不影響功能，可順手清理。
   - 熱路徑 lock 分散、login/place_order 例外處理仍可能影響 run loop 等，維持原有設計哲學（無需立即重構）。

## 2. UAT 進入判斷（更新版，2026-06-16）

### 對自己 consuming app 的整合 UAT
**強烈建議進入**（可進行小資金 paper trade → 小口實盤 UAT）。

理由：
- 核心正確性與安全邊界（kernel-owned force-flatten、position_qty 單一事實來源、pending 期間不重複 entry、reconnect 對帳 hygiene、signal validation）皆有實作 + 73 個 kernel tests + no-shioaji 強制檢查護航。
- 文件已補齊「Live Trading Safety + Known Limitations + Go-Live Checklist」，outsider 誤用風險大幅下降。
- `get_state_snapshot()` + 強力「勿直接 mutate」警告已到位。
- 提供 minimal_live 範例骨架 + .env.example + 明確 secrets 指引。

### 對「公開 GitHub + 鼓勵外部人士拿去實盤」
**已達可考慮公開鼓勵的門檻**。

原 CodeReview#2 建議優先處理的前 4 項（SPEC 更新、README Live Safety + checklist、主要失敗情境文件、state snapshot + 強力唯讀警告）皆已實作到「outsiders 看完文件不會誤解風險」的程度。validation guards（第 5 項）與 CI lint（第 6 項）也已補上。

**公開使用時仍建議**：
- 在 README 與 release note 置頂強烈提醒：「**務必完整閱讀 docs/LIVE_SAFETY.md 與執行 Go-Live Checklist**」與「**一律使用 get_state_snapshot() 觀察狀態，切勿直接修改 engine 屬性**」。
- 維持「0.x 實驗期」定位與「風險自負」免責聲明。
- 未來可考慮在 0.x 後期逐步把熱門狀態欄位改為 read-only property（或至少加嚴格 deprecation 機制），進一步降低狀態風險。

## 3. 後續建議（非 blocker，可選優先序）

1. 順手清理 `src/trading_engine/core/side_effect_ports.py:76` docstring 內的 "theman" 字樣。
2. 在 README「Secrets」或使用章節補充說明 logging `configure_root=False` 的使用情境（避免影響 consuming app 既有 logging 設定）。
3. 可選：在 STRATEGY.md 或 LIVE_SAFETY.md 增加「如何在 telemetry 層安全 snapshot + 發 CRITICAL alert」的簡短程式碼範例（5–8 行）。
4. CI mypy 範圍可逐步擴大（目前僅掃幾個核心檔 + non-blocking），視需求而非急務。
5. 長期（接近 1.0）：依 STRATEGY.md roadmap 收斂 Strategy Protocol surface。

## 總結

這一輪修復非常精準且有效。特別值得肯定的是：
- `docs/LIVE_SAFETY.md` 的完整度與實用性。
- 多處文件對「position 模型限制」與「狀態唯讀觀察」的一致性強調。
- signal validation 與 state snapshot 的實作 + 測試 + 文件三管齊下。

本專案已從「從 theman 抽離的內部執行元件」穩健進化為「有自己生命、核心正確性有測試護航、文件對實盤失敗模式透明的獨立 trading-engine kernel」。

對作者自己的實盤流程來說，現在是合理且有信心的下一步（paper trade → 小口實盤 UAT）。

對公開社群而言，只要搭配強烈的文件警告與 checklist 導引，已具備作為「期貨執行 kernel 技術參考實作」的公開價值。

---

**附錄：本次 re-review 參考的關鍵檔案路徑（選錄）**

- `README.md:31`（Live Trading Safety & Known Limitations）
- `README.md:37`（Go-Live Checklist）
- `SPEC.md:85`（§4.2.1 Position Model Scope）
- `SPEC.md:158`（CI 描述更新）
- `docs/LIVE_SAFETY.md`（全新，完整失敗情境表）
- `docs/STRATEGY.md`（Protocol 說明 + MUST/MUST NOT + roadmap）
- `docs/DESIGN.md:104`（Position model limitations + State observation）
- `src/trading_engine/engine.py:225`（get_state_snapshot）
- `src/trading_engine/order_executor.py:19`（_validate_order_signal）
- `src/trading_engine/logging_setup.py:14`（LOGGER_NAME = "trading_engine"）
- `src/trading_engine/core/types.py:73`（EngineStateSnapshot frozen）
- `.github/workflows/tests.yml`（quality job + no-shioaji guard）
- `tests/runtime/test_state_snapshot.py`、`tests/runtime/test_signal_validation.py`
- `tests/test_no_shioaji_core_import.py`
- 實測：`python3 run_tests.py` → 73 tests OK

如需針對本 re-review 再進行下一輪修復或產出 patch，請告知。