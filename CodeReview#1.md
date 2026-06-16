總結：目前水準作為「從 theman 抽出的內部共用元件」是好的，但以「獨立 repo + 交易引擎最高標準」來看，還不足以直接成為一個 standalone production-grade repo。

它有真實交易經驗的痕跡（reconcile、pending 超時、IOC、opening window、tick_type 推斷、重連對帳等），結構也乾淨，但狀態機在核心不變量（position size、session force flatten 所有權、broker 中立性）上有結構性缺口，加上文件與打包仍帶強烈 monorepo 痕跡。

下面用你指定的三個維度，用最嚴格的交易引擎標準（正確性、冪等性、狀態一致性、可審計、fail-safe、跨 broker 隔離）逐一檢視。

1. README.md 調整（目前明顯不合格）

現況問題（README.md (/Users/tim_chuang/workaround/future/trading-engine/README.md)）：
• 完全寫成「theman 的附屬品」（../theman、pip install -e ../、155 tests 靠 theman/run_tests.py 跑）。
• 安裝與使用範例都假設 monorepo 上下文。
• 沒有獨立安裝（PyPI 或 git）、沒有版本相容性說明、沒有「這是 kernel，只負責 execution state machine」的清晰邊界宣告。
• 缺少 license 宣告、quickstart for backtest-only 使用者、以及「如何貢獻新 broker adapter」的最小指引。

建議調整方向：
• 把 README 寫成獨立專案視角的第一入口。
• 明確 Scope / Non-Goals（可直接參考 SPEC.md 第 2-3 節，濃縮版）。
• 提供三種使用情境：Live（shioaji）、Backtest（mock）、Pure kernel test（MagicMock）。
• 加入「安裝」「最小可跑範例（不需要 shioaji）」「如何注入自己的 OrderAdapter / Calendar / Telemetry」。
• 測試章節要改成「本 repo 有 37 個 kernel tests（python run_tests.py），完整整合測在消費端 repo」。
• 加上 Status（0.x 實驗期）、相容性、保證事項（e.g. "engine 保證在 is_pending 時不會發第二個 entry" 這類不變量）。

SPEC.md 其實寫得比 README 好很多（定位、依賴方向、公開 API、待辦都清楚），建議讓 README 指向 SPEC.md，並把 README 做成「5 分鐘懂 + 怎麼用」的角色。

2. 資料夾結構

目前結構（src/trading_engine/ + tests/ + SPEC.md + pyproject.toml）大方向正確且乾淨，符合「kernel 只做 state machine + 窄 ports」的原則。

優點：
• core/（types, ports, strategy, order_events, runtime_config, side_effect_ports, audit）隔離良好。
• adapters/ 只負責 order 建構（這點做得對）。
• calendar/ 已獨立（TaifexMarketCalendar + Port Protocol）。
• testing/ helpers/defaults 提供 kernel test 隔離，很好。
• 沒有把 strategy 邏輯、storage、alert 塞進來。

問題與嚴格建議：
• exchange_time.py 只做 from ...calendar.taifex import *，是向後相容的權宜之計，長期應該 deprecated 或明確標註「compat layer」。
• plugins.py（entry point 載入 strategy）放在 trading-engine 裡面有點尷尬（它本來就說 strategy 是 app/plugin 層）。這比較適合移到「策略生態」或至少文件強調這是可選的 discovery 機制，不是核心。
• 缺少 LICENSE、py.typed（如果要認真做 typing）、__version__ 暴露。
• 缺少 docs/ 或至少在 repo 根放一個 docs/DESIGN.md 把狀態機不變量、transition 表、reconcile 策略寫清楚（目前只有 SPEC.md 的高層級描述）。
• tests/ 只有 37 個，全部是 kernel 級（正確），但缺少更多 adversarial 測試（duplicate callback、reconnect 期間 fill 與 timeout 競態、qty>1、方向反轉等）。

整體來說結構已足以獨立，但要達到「可長期維護的獨立 kernel」還要補 hygiene 與文件。

3. 狀態機完整性（最嚴格標準檢視）

這是核心。TradingEngine = OrderExecutorMixin + SessionMixin，狀態散在很多 bool + string 上（is_pending、exit_pending、pending_intent、has_position、position_dir、block_new_entry 等），沒有顯式 State / Transition 表。

做得好的地方（真實經驗）
• on_tick 內 lock 保護 _arm_pending + strategy 決策，防止雙 tick 同時進 pending（P2-2 註解）。
• Order ID matching 相當嚴謹（_matches_pending_order + 多種 payload fallback）。
• Partial fill 處理（filled_qty 累計，IOC 未完全成交前不解鎖）有前置考量。
• Timeout + reconnect 都有 _reconcile_pending_trade（update_status + order_deal_records 雙保險）。
• RiskGate 注入策略 + vol_threshold + session 時間旗標，決策與執行分離。
• 每日狀態重置用交易所本地交易日（trading_day_for_daily_reset），並在 tick 路徑觸發。
• Exit 重試只限 exit、不重試 entry（「漏單是成本」哲學正確）。

用交易引擎最高標準的嚴重問題（必須修）

1. Position size 完全沒有模型（最嚴重缺陷）
   • sync_positions 讀到 matched.quantity 卻只拿來 log，內部狀態只有 has_position + position_dir + entry_price，沒有 current_position_qty。
   • pending_qty / filled_qty 只追蹤「這筆 pending order」，不是持倉規模。
   • _apply_deal_fill entry 時直接設 has_position = True，完全不管成交了幾口。
   • 註解寫「多口管理前置」，表示作者知道，但目前狀態機不支援 scale-in / partial exit / 正確的 position accounting。
   • 這對任何認真的期貨引擎都是致命。即使目前策略只做 1 口，也必須在 kernel 層把 qty 當成一等公民。

2. Session force-flatten 所有權不明確（安全邊界缺失）
   • RiskGate 有 force_flatten，Strategy Protocol 有 session_force_flatten_signal。
   • 但 host 從未主動在 force_flatten_time 時發出 exit signal。
   • 強制平倉的責任被推給每個 strategy 實作。這違反「kernel 負責不變量（must be flat by X）」的原則。
   • 正確做法：kernel 層在 tick 路徑或 background watchdog 發現「force_flatten_time 已到 + 有倉 + 沒在 exit_pending」時，自己產生一個 intent=exit 的 OrderSignal（可允許 strategy 提供客製價格/理由，但 host 擁有觸發權）。

3. Shioaji 耦合滲透到非 adapter 層（破壞 broker-agnostic）
   • session.py:162-164：import shioaji as sj; is_long = matched.direction in (sj.Action.Buy, "Buy") —— 即使你注入 Mock，這行在對帳時還是會 import。
   • engine.py 多處 lazy import shioaji + 直接操作 self.api.subscribe(..., sj.QuoteType.Tick)、sj.Shioaji(...)、set_order_callback 等（start、重連、no-tick watchdog）。
   • BrokerPort Protocol 寫得很好（文件化窄介面），但實際核心路徑還是假設 shioaji 回呼格式與 event code（12/13）。
   • 新 broker adapter 光做 order construction 不夠，event 處理與 position list 格式也會被拉進來。

4. 狀態是隱式而非顯式，轉移表不存在
   • 沒有 enum 描述 "Idle / PendingEntry / PendingExit / Flat / Long / Short + cooldown" 之類的合法組合。
   • 很多 guard 只靠 if not self.is_pending: return + order_id 比對，缺少「這個狀態下不該收到這個 event」的明確防護 + logging。
   • 這使得審計所有邊界（entry 時收到 exit deal？已經 flat 還收到 fill？reconnect 期間有兩個 pending？）變得困難。

中等但重要的問題
• 併發控制細節多但不夠集中：on_tick 拿 lock，order worker 不拿，reconcile 拿再放、background timeout 拿。雖然大部分有 _still_own_pending 守衛，但容易在 refactor 時出錯。建議考慮把「所有會改變 trading state 的操作」都經由少數幾個明確的 locked 入口，或用一個明確的 State 物件。
• _event_order_id 的 fallback 層級太多（trade_id / status.id / order.id），不同券商或不同 stat 很容易誤配。
• sync_positions 只取「第一個匹配的非零部位」，如果同 contract 有多筆或不同 direction，行為未定義。
• ATR refresh、trend refresh 都在 daemon thread 做，失敗只 warning，沒有 circuit breaker 或對狀態的明確影響。

小問題 / 改善點
• 部分 pending 狀態在 lock 外 snapshot 後再動作（_reconstruct_pending_signal 等），雖有 guard 但心智負擔高。
• pending_trade 物件在 reconcile 時被拿來比對，但如果券商端 trade 物件有狀態變化，容易 stale。
• 沒有對「同一個 order_id 連續兩次 deal callback」的明確去重（目前靠 filled_qty 累加 + pending 清掉後的 guard）。
• 缺少對「成交數量與 pending_qty 不一致」的防呆（真實世界券商偶爾會報錯 qty）。

測試目前 37 個全過（很好），但覆蓋集中在「快樂路徑 + 少量 guard」。缺少大量 adversarial 案例，這對交易引擎是危險的。

結論與建議優先順序

可以成為獨立 repo 的基礎已經存在（抽離乾淨、ports 設計正確、SPEC 寫得好、測試可獨立跑）。

但以最嚴格的交易引擎標準，現在還不夠，主要卡在：
• Position quantity 模型缺失（正確性）
• Force flatten 與其他硬性 session 邊界的所有權缺失（安全）
• Broker 耦合未完全隔離在 adapters + 窄 ports 之下（可替換性）
• 狀態機仍是隱式 + 文件未從 monorepo 視角轉向 standalone

建議優先修復順序（想成為獨立 repo 就先做這些）：
1. 在 core/types.py 引入 Position（含 qty）或至少讓引擎內部有 current_position_qty，並讓 sync_positions 與 _apply_deal_fill 正確維護它。所有用到 position 的地方（包含 RiskGate、strategy snapshot）都要反映 qty。
2. 把 session force flatten（以及可能未來的 hard stop）改成 host 擁有主動權的機制（可讓 strategy 客製化 signal）。
3. 清理 shioaji 直接 import 與具體型別使用，全部集中到 adapters 與「shioaji-specific event normalizer」（可新增一個 ShioajiEventAdapter 或類似）。
4. 在 SPEC.md 或新文件加「State Transitions」表格 + 關鍵不變量清單。
5. 重寫 README 成獨立專案視角 + 補 LICENSE + 暴露 version + 讓 pyproject.toml 更完整（classifiers, license）。
6. 大幅增加 runtime/ 下的 adversarial tests（尤其是 reconnect + callback 競態 + partial qty + wrong order id 各種變形）。

做完 1-3 + 5 之後，這份專案就有資格說「這是一個獨立、可被其他專案依賴的 futures execution kernel」，而不是「theman 抽出來的那塊」。

需要我針對上面任何一個嚴重問題（尤其是 position qty 模型或 force-flatten 所有權）提出具體的修改設計或 PR plan，隨時告訴我。