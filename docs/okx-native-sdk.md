# OKX 原生 SDK 方向

本项目现在把"直接对接 OKX"当作 MVP 的首选路径。

## 为什么

对于单交易所、OKX 优先的交易副驾驶来说，直连比走 Hummingbot 更简单：
- 抽象层更少
- 对 OKX 原生错误更好调试
- 对账户同步、杠杆设置、下单的控制更精细
- 更容易保留 OKX 独有语义

## 选用的 SDK

包：
- `python-okx==0.4.1`

从项目公开元数据确认：
- 覆盖 OKX v5 REST 端点
- 带 websocket 支持
- 通过 `flag="1"` 支持模拟盘
- 提供 `AccountAPI` / `TradeAPI` / `MarketAPI` 等 Python 类

## 本地配置

必填环境变量：
- `USE_OKX_NATIVE=true`
- `OKX_API_KEY`
- `OKX_API_SECRET`
- `OKX_PASSPHRASE`
- `OKX_FLAG=1` 模拟盘，`0` 真实盘
- `OKX_TD_MODE=cross` 或 `isolated`
- `OKX_SYMBOL=BTC-USDT-SWAP`
- `AUDIT_LOG_PATH=var/logs/audit/events.jsonl`
- `SIGNAL_SHARED_SECRET=...` 用于 `/signal` 鉴权
- `SIGNAL_IDEMPOTENCY_PATH=var/state/signal_ids.txt`
- `OKX_WS_URL=wss://ws.okx.com:8443/ws/v5/private`
- `RECONCILE_POLL_INTERVAL_SECONDS=30`

默认的安全开关：
- `EXECUTION_ENABLED=false`
- `PAPER_MODE=true`
- `TRADING_HALTED=false`

## 已实现的原生模块

- `src/agent_trader/okx_client.py`
- `src/agent_trader/okx_account_sync.py`
- `src/agent_trader/okx_execution_service.py`
- `src/agent_trader/okx_order_service.py`
- `src/agent_trader/okx_ws.py`
- `src/agent_trader/okx_ws_transport.py`
- `src/agent_trader/reconcile_job.py`
- `src/agent_trader/reconcile_scheduler.py`
- `src/agent_trader/runtime_supervisor.py`
- `src/agent_trader/runtime_daemon.py`
- `src/agent_trader/runtime_entry.py`
- `src/agent_trader/demo_smoke.py`
- `src/agent_trader/audit_log.py`
- 原生执行现在已经：
  - 查 `ctVal`，把 USD notional 正确换算成 OKX 合约张数
  - 读账户 `posMode`，必要时自动填 `posSide`
  - 以 `(inst_id, td_mode, pos_side)` 为 key 缓存杠杆设置
  - 开仓时附带 TP/SL algo order
  - 平仓时带 `reduceOnly=true`
- websocket / 运行时脚手架：
  - 为 orders / positions / account 构造私有登录 + 订阅 payload
  - 支持 handler 注册、ping、重连和 async run-once 骨架
  - 提供 transport 抽象以便接入真实 websocket 连接
  - 提供 daemon / supervisor / entry builder 骨架，供长运行编排使用
  - 通过配置暴露 ws URL，方便在 demo / live 之间切换
- 对账 / 运行时脚手架：
  - 下单完成后立即对账
  - 批量对账 job 覆盖未完成订单
  - 调度器骨架负责周期性轮询
  - supervisor 骨架协调 ws 循环 + 对账循环
  - demo smoke helper 会执行 demo 验证并输出对账摘要
- `src/agent_trader/main.py` 里暴露的原生辅助函数：
  - `make_okx_client()`
  - `okx_account_state_payload()`
  - `run_okx_native_signal_pipeline()`
  - `run_primary_signal_pipeline()`
  - `process_signal_request_payload()`

## 原生路径后续要做的事

1. 把 `build_runtime_daemon(...)` 接到真实 CLI / 进程入口
2. 用真实 demo 凭证跑一条 `run_demo_smoke_test(...)` 流程
3. paper → demo → 极小真实仓位，逐步放开
4. 审计事件里丰富 proposal / risk 快照，方便交易后分析
5. 为长运行部署加持久化幂等记录的清理 / TTL 策略
