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
