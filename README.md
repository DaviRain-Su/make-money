# OKX + Hummingbot + AI Agent MVP

这是一个基于 OKX 永续合约的 AI 辅助交易副驾驶（copilot）原型。仓库里同时保留了两条执行路径：

- **主路径**：通过 `python-okx` SDK 直连 OKX 原生 API（默认）
- **备用路径**：走 Hummingbot 的连接器抽象层

核心原则：
- 硬风控规则说了算（通过 / 拒绝）
- AI 只能给建议，**不能绕过风控硬限**
- OKX 原生 API 是默认执行路径
- 下单数量以 OKX 合约面值（`ctVal`）为单位换算，而不是基础币数量
- 默认开着 paper / demo 模式

当前里程碑：
- 第一家交易所：OKX
- 通过 `python-okx` 接入原生 API
- `main.py` 的默认执行路径已切到原生 OKX
- `okx_perpetual`（Hummingbot 连接器）保留作为备用
- 确定性风控引擎已实现并测试
- Hummingbot API 客户端封装完成
- OKX 账户 / 持仓快照同步已完成（原生 + Hummingbot 两版）

## 仓库结构

- `src/agent_trader/models.py` — 领域模型
- `src/agent_trader/risk.py` — 确定性硬风控检查
- `src/agent_trader/config.py` — 从环境变量加载配置
- `src/agent_trader/hbot_client.py` — Hummingbot API 轻量封装（账户/连接器/持仓/组合）
- `src/agent_trader/account_sync.py` — 把 Hummingbot 的 OKX 数据映射成本地 `AccountState`
- `src/agent_trader/okx_client.py` — 基于 `python-okx` 的 OKX 原生 SDK 封装
- `src/agent_trader/okx_account_sync.py` — 把 OKX 原生账户 / 持仓返回映射成本地 `AccountState`
- `src/agent_trader/okx_execution_service.py` — OKX 市价单执行助手（`ctVal` 换算 + `attachAlgoOrds` 止损止盈）
- `src/agent_trader/proposal_service.py` — 从 `StrategySignal` 构造 `TradeProposal`（按止损距离定仓位、扣除剩余额度、区分 OPEN/CLOSE）
- `src/agent_trader/control_state.py` — 持久化的暂停开关（`var/state/control.json`）
- `src/agent_trader/admin_api.py` — 面向 Hermes 的管理面（HMAC + nonce，halt/resume/status/manual_trade，分级确认）
- `src/agent_trader/signal_security.py` — `/signal` 的共享密钥鉴权 + 幂等控制
- `src/agent_trader/web_ui.py` — 审计事件 tail + 分类 + 统计（驱动本地 dashboard）
- `src/agent_trader/okx_ws.py` + `src/agent_trader/okx_ws_transport.py` — OKX 私有 ws 登录/订阅逻辑 + transport 适配
- `src/agent_trader/reconcile_job.py` + `src/agent_trader/reconcile_scheduler.py` — 批量对账 + 周期调度骨架
- `src/agent_trader/runtime_supervisor.py` + `src/agent_trader/runtime_daemon.py` + `src/agent_trader/runtime_entry.py` — 长运行 daemon 协调层
- `src/agent_trader/demo_smoke.py` — OKX demo 环境烟雾测试助手
- `src/agent_trader/main.py` — 控制平面骨架 + 可选的 FastAPI 应用
- `tests/` — 对应每个模块的单元测试
- `docs/architecture.md` — 系统边界和流程
- `docs/okx-hummingbot-setup.md` — 交易所和连接器假设
- `docs/okx-native-sdk.md` — OKX 原生 SDK 的选型与模块清单
- `prompts/` — AI 初始 prompt 模板

## 安全模型

系统刻意保守：
- 只支持一家交易所：OKX
- 只支持一个连接器：`okx_perpetual`
- 只支持一个市场：`BTC-USDT-SWAP`
- 不提交任何真实密钥
- 默认不做真实下单
- 所有下单路径（策略的 `/signal` + Hermes 的 `/admin/manual_trade`）**都要过** `evaluate_trade` 这一道硬风控
- `RiskLimits.trading_halted`（环境变量）和 `control.json`（运行时持久化）两个暂停开关任一生效即拒单

### 保证金感知风控（Step 1）

`AccountState` 除了总权益、日内盈亏、持仓敞口，还会携带 OKX 返回的 **可用保证金 `availEq`**、**账户级保证金率 `mgnRatio`** 和 **已用初始保证金 `imr`**。风控引擎据此多加三道闸门：

- `RISK_MIN_MARGIN_RATIO`：账户级 `mgnRatio` 低于该值时拒单。数值越大越健康，接近 1.0 即临近强平。默认 `0`（关闭）。
- `RISK_MAX_MARGIN_UTILIZATION`：`(已用保证金 + 新仓初始保证金) / 总权益` 超过该值时拒单。默认 `1.0`（关闭）；cross margin 多合约建议调到 `0.5`。
- `RISK_MIN_AVAIL_EQUITY_USD`：可用保证金低于该值时拒单。默认 `0`（关闭）。

另外：**如果新仓所需初始保证金本身就超过可用保证金**，即使未设阈值也会被直接拒（`insufficient available margin for new position`）。

这些检查只在账户同步层能拿到相应字段时生效。OKX 原生路径已接入；Hummingbot 路径暂时留空（返回 `None`），等对应字段补上后才会触发。

### 多合约支持（Step 2）

- `/signal` payload 可带 `symbol` 字段；未传则回落到 `OKX_SYMBOL` 默认值
- `/admin/manual_trade` 的 body 同样支持 `symbol`
- `OKX_ALLOWED_SYMBOLS`（逗号分隔）设了就是白名单；**不在白名单里直接被风控拒**（`symbol not in allowed list`）。留空 = 不限制
- `AccountState.positions_by_symbol` 把敞口按合约展开（OKX 原生已接入）
- `RISK_MAX_NOTIONAL_PER_SYMBOL_USD`：单合约名义金额上限，防止单个合约押太重
- `RISK_MAX_NOTIONAL_USD` 仍是账户总名义金额上限（跨合约累计）
- Dashboard 在"按合约敞口"卡片里按 USD 倒序展示每个合约的当前名义金额
- 多合约 cross margin 场景下，强烈建议把 `RISK_MIN_MARGIN_RATIO` / `RISK_MAX_MARGIN_UTILIZATION` / `RISK_MIN_AVAIL_EQUITY_USD` 这三道保证金闸门同步打开

### 强平距离 + 并发持仓数（Step 3）

- `AccountState.positions_detail` 把每个持仓的 `markPx` / `liqPx` / `distance_pct`（`|mark-liq|/mark`）/ `side` 单独记下来
- `RISK_MIN_LIQUIDATION_DISTANCE_PCT`：任意持仓到强平价的距离小于该比例时，禁止开新仓（平仓和减仓不受限）。防止在某个合约已经濒危时继续加风险
- `RISK_MAX_OPEN_POSITIONS`：最多同时持有多少个不同合约。到上限后只能加仓既有合约或平仓，不能再开新合约
- Dashboard 的"按合约敞口"卡片现在同时展示方向、markPx、liqPx 和距离（小于 5% 红色，小于 15% 黄色，其余绿色）

## 策略信号源（EMA/ATR）

`src/agent_trader/strategy.py` + `strategy_runner.py` 实现了一个可单测的确定性策略：

- 双 EMA 交叉判方向（`STRATEGY_FAST_EMA` / `STRATEGY_SLOW_EMA`）
- ATR 定止损止盈（默认 2×ATR 止损，3×ATR 止盈，3R 盈亏比）
- **只看收线完的 K 线**（OKX `confirm="1"`），不会在形成中的 bar 上闪烁
- 幂等键：`client_signal_id = "ema_atr:SYMBOL:bar:bar_ts:side"`，同一根 K 线、同一方向只会发一次

调用链：
```
strategy_runner.run_strategy_once(client, symbols, bar, limit, config, dispatch)
   ↓ 每个 symbol
     client.get_candles()  (OKX)
     parse_okx_candles() → oldest-first, 过滤未收线
     generate_ema_atr_signal() → Optional[StrategySignal]
   ↓ 有信号就 dispatch（默认调 process_signal_request_payload）
     → /signal 管线 → 风控 → 执行或拦截
```

入口：
- Python：`from agent_trader.main import run_strategy_poll; run_strategy_poll()` 做一次轮询
- HTTP：`POST /admin/strategy/poll`（走 admin HMAC 鉴权），Hermes 可以按需触发
- 长运行：可以和 `runtime_daemon` 串起来做周期调度，目前 repo 暂未默认挂上

多合约：默认用 `STRATEGY_SYMBOLS`，空则回落到 `OKX_ALLOWED_SYMBOLS`，再空则只处理 `OKX_SYMBOL`。

安全默认：`STRATEGY_ENABLED=false`。开启前建议：
1. paper 模式 + demo 账户
2. 对每个合约把 K 线拉下来，手动复核 EMA 交叉点是否和预期一致
3. 观察 `strategy_poll` 审计事件 + 被风控拦下的信号，确认策略不会和风控打架
4. 再把 `EXECUTION_ENABLED=true`

## 和 freqtrade 集成

[freqtrade](https://www.freqtrade.io/) 的强项是策略 R&D：回测、Hyperopt、上百个社区策略、FreqAI。我们的强项是 OKX 原生深度 + 硬风控 + 面向 AI agent 的管理面 + cross-margin 多合约安全网。把两个串起来各取所长：**freqtrade 发信号，agent_trader 下单。**

**做法**：freqtrade 用 webhook 推到我们的 `POST /signal/freqtrade`，我们自带一个 adapter 把 freqtrade 的字段（`pair` / `direction` / `open_rate` / `stop_loss` / `leverage` / `exit_reason`…）翻译成内部 `/signal` 格式，风控和审计完全一致。

- pair 映射：`BTC/USDT` 或 `BTC/USDT:USDT` → `BTC-USDT-SWAP`（已是 `X-Y-SWAP` 格式则原样透传）
- 方向：`long` → `buy`，`short` → `sell`；exit 事件自动翻转方向并把 `position_action` 置为 `CLOSE`
- 止损：优先用 payload 里的 `stop_loss`；没传则 `stop_loss_pct` 换算；再没有就默认 2% 兜底
- 止盈：payload 没传时按 3R 倒推（`stop_distance * 3`）
- `client_signal_id = "freqtrade:{trade_id}:{OPEN/CLOSE}:{symbol}:{side}"`，天然幂等

**freqtrade 端 `config.json` 示例**：

```json
{
  "webhook": {
    "enabled": true,
    "url": "http://127.0.0.1:8787/signal/freqtrade",
    "format": "json",
    "retries": 3,
    "retry_delay": 1,
    "webhookentry": {
      "type": "entry",
      "trade_id": "{trade_id}",
      "pair": "{pair}",
      "direction": "{direction}",
      "open_rate": "{open_rate}",
      "leverage": "{leverage}",
      "stop_loss": "{stop_loss}",
      "stop_loss_pct": "{stop_loss_pct}",
      "enter_tag": "{enter_tag}"
    },
    "webhookexit": {
      "type": "exit",
      "trade_id": "{trade_id}",
      "pair": "{pair}",
      "direction": "{direction}",
      "close_rate": "{close_rate}",
      "exit_reason": "{exit_reason}"
    }
  }
}
```

如果你设置了 `SIGNAL_SHARED_SECRET`，freqtrade 还要在 `webhook` 块里加 `"headers": {"x-signal-secret": "你的密钥"}`。

**运行时拓扑**：
```
freqtrade (容器 A，负责策略)       agent_trader (容器 B，负责执行+风控)
──────────────────────────        ────────────────────────────────
populate_entry_trend              POST /signal/freqtrade
populate_exit_trend               ↓
enter/exit webhook fires  ──────> translate_freqtrade_webhook
                                   ↓
                                   /signal 管线：幂等 → 风控 → 执行 → 审计
                                   ↓
                                   OKX
```

两个容器独立：freqtrade 挂了，已开仓位不会失控；agent_trader 挂了，freqtrade 就停止接单。两个系统共用一份审计日志（由 agent_trader 写）。

**可选的其他用法**：
- 只用 freqtrade 回测，不实盘运行——选出参数后把策略抄到我们的 `strategy.py`
- 只用 agent_trader 的风控——freqtrade 继续自己下单到另一个账户，我们的 `/admin/manual_trade` 作为应急通道

### 反向 adapter（被风控拦下时同步 freqtrade 状态）

freqtrade 发出 webhook 时，它自己的内部 DB 已经假设这单开成了。如果我们风控层拒绝执行，freqtrade 那边就留下一个幻影持仓。`freqtrade_reconciler.force_exit_trade` 会在这种情况下自动调 freqtrade 的 `/api/v1/forceexit` 把那笔虚拟仓位清掉。

开启方式：
```env
FREQTRADE_API_URL=http://freqtrade.local:8080
FREQTRADE_API_USERNAME=...
FREQTRADE_API_PASSWORD=...
FREQTRADE_RECONCILE_ON_BLOCK=true
```

仅在 `execution.status == blocked` 且 payload 里带有 `trade_id` 时触发。调用失败会写 `freqtrade_reconcile` 审计事件，不会影响正常的 `/signal` 响应。

## 告警通道

为 "danger" 级事件提供一个统一的 webhook 出口：
- 策略或外部信号被风控拦下
- `/ui/halt` 或 `/admin/halt` 被触发
- 其他 `classify_signal_result` 判定为 danger 的情况

配置：
```env
ALERT_WEBHOOK_URL=https://my-hermes-relay/incoming
ALERT_TIMEOUT_SECONDS=5
```

Webhook payload 示例（POST JSON body）：
```json
{
  "event_type": "signal_blocked",
  "level": "danger",
  "symbol": "BTC-USDT-SWAP",
  "side": "buy",
  "risk_reasons": ["notional limit exceeded"],
  "execution_status": "blocked",
  "client_signal_id": "..."
}
```

Fire-and-forget 语义：投递失败不会影响下单流程，审计日志仍记录原始事件。Hermes / Telegram 中继 / PagerDuty / 自定义 Slack relay 都可以订阅这个 URL。

## 回测

`src/agent_trader/backtest.py` 提供一个走 walk-forward 的回测引擎，**用的是同一个风控引擎**。目的不是找 alpha（freqtrade 在那件事上更强），而是"告诉我 freqtrade 调出来的策略里，哪些会被我们的风控拦住"。

```python
from agent_trader.backtest import run_backtest
from agent_trader.strategy import Candle, EmaAtrConfig, generate_ema_atr_signal
from agent_trader.models import RiskLimits

candles = [Candle(ts=..., open=..., high=..., low=..., close=...) for _ in range(...)]
report = run_backtest(
    signal_generator=lambda sym, bars: generate_ema_atr_signal(sym, bars, EmaAtrConfig()),
    candles_by_symbol={"BTC-USDT-SWAP": candles},
    initial_equity_usd=10_000.0,
    risk_limits=RiskLimits(
        max_notional_usd=3000.0,
        max_leverage=5.0,
        daily_loss_limit_pct=5.0,
        max_slippage_bps=50.0,
        max_notional_per_symbol_usd=1500.0,
    ),
    allowed_symbols=("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
    risk_fraction=0.1,
)
print("PnL:", report.total_pnl_usd)
print("Win rate:", report.win_rate)
print("Blocked by reason:", report.block_reasons)
```

报告字段：`signals_total` / `signals_approved` / `signals_blocked` / `block_reasons`（按原因计数）/ `closed_trades`（每笔含 entry/exit/reason/PnL）/ `win_rate` / `max_drawdown_pct` / `total_pnl_usd` / `blocked_signals`（明细）。

## Hermes 管理面

Hermes 跑在独立进程（不在这个 repo 里）。它只能通过 HMAC 签名的 HTTP 调用这里的服务，**既不持有 OKX 密钥，也改不了 `risk.py`**。

- `GET  /admin/status` — 返回控制状态 + 执行开关
- `POST /admin/halt` — 打开持久化暂停开关，后续所有下单被拒，理由 `trading halted`
- `POST /admin/resume` — 关闭暂停开关
- `POST /admin/manual_trade` — 从 Hermes 的参数拼一个 `StrategySignal`，走和策略信号完全相同的管线（风控依然生效）

鉴权：每个请求必须带 `X-Admin-Timestamp`、`X-Admin-Nonce`、`X-Admin-Signature` 三个头。
签名公式：`hmac_sha256(ADMIN_SHARED_SECRET, "{timestamp}.{nonce}.{path}.{canonical_json_body}")`。
nonce 一次性（持久化到 `ADMIN_NONCE_PATH`），timestamp 必须落在服务器时钟 60 秒窗口内。

manual_trade 分级（阈值均可通过 env 调整）：
- `< ADMIN_SMALL_TRADE_USD`（默认 500 USD）— 直接执行
- `>= ADMIN_SMALL_TRADE_USD` — body 需带 `confirmation: "confirmed"`
- `>= ADMIN_LARGE_TRADE_USD`（默认 5000 USD） — 还必须带 `pin`，且值等于 `ADMIN_SHARED_SECRET`

所有管理操作都会写一条 `admin_action` 审计事件。

## 本地 Dashboard

同一个 FastAPI 应用顺便提供了一个最小的只读（+ 暂停按钮）Web 面板。生产部署时把服务绑到 `127.0.0.1`，`/ui/*` 端点会拒绝非本地请求。

- `GET  /ui/` — 单页仪表盘（状态、HALT 按钮、账户快照、审计流）
- `GET  /ui/summary` — 聚合的状态 + 账户 + 计数器 + 最近事件
- `GET  /ui/events?limit=N` — 以 JSON 返回最近的审计事件
- `POST /ui/halt` / `POST /ui/resume` — 翻转持久化暂停开关（仅本地可用，写 `admin_action` 审计，`source: local_ui`）

UI **不能下单**——真要下单就走 `/signal`（策略）或 `/admin/manual_trade`（Hermes）。仪表盘存在的意义是显示 OKX 账户页看不到的东西：被风控拦下的信号、账户对账差异、暂停历史。

## 运行测试

```bash
PYTHONPATH=src python3 -m unittest -v
```

## 下一步规划

1. 独立部署 Hummingbot，把它的 API 暴露出来
2. 补上带认证的 Hummingbot API 客户端
3. 接入一个简单的策略输出作为信号源
4. 加入 AI 行情判断和建议审核
5. 完善审计日志 + paper 回测循环

## 走向实盘的推荐顺序

别一上来就全自动，建议按下面顺序递进：
1. 跑单元测试
2. 本地 `curl /signal` 提交测试信号
3. 检查 `AUDIT_LOG_PATH` 下追加的 JSONL 审计事件
4. paper 执行路径跑通，返回 payload 里 reconciliation 字段正常
5. 验证 `OKX_WS_URL` 上的 websocket 登录 / 订阅流程
6. 用安全的测试 transport 跑一遍 ws manager 的 `run_once()` / `reconnect_async()`
7. 用安全的测试 transport + 假的未完成订单跑 `RuntimeSupervisor.run_iteration()`
8. 用假组件跑 `RuntimeDaemon.run_once()`
9. 用 `build_runtime_daemon(...)` 组装完整运行时骨架
10. 用 OKX demo 凭据跑 `run_demo_smoke_test(...)`
11. 切到 OKX demo 模式（`OKX_FLAG=1`）
12. 在 demo 环境对照订单状态校对
13. 用极小仓位切 OKX 真实环境（`OKX_FLAG=0`）
14. 只有在日志 + 风控长期表现可靠之后才扩大规模
