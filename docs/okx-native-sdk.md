# OKX Native SDK Direction

This project now treats direct OKX integration as the preferred MVP path.

## Why

For a single-exchange OKX-first trading copilot, direct integration is simpler than routing through Hummingbot:
- fewer abstraction layers
- easier debugging against OKX-native errors
- tighter control over account sync, leverage setting, and order placement
- easier to keep OKX-specific semantics intact

## Chosen SDK

Package:
- `python-okx==0.4.1`

What public project metadata confirms:
- covers OKX v5 REST endpoints
- includes websocket support
- supports demo trading using `flag="1"`
- provides Python classes like `AccountAPI`, `TradeAPI`, and `MarketAPI`

## Local config

Required environment variables:
- `USE_OKX_NATIVE=true`
- `OKX_API_KEY`
- `OKX_API_SECRET`
- `OKX_PASSPHRASE`
- `OKX_FLAG=1` for demo, `0` for live
- `OKX_TD_MODE=cross` or `isolated`
- `OKX_SYMBOL=BTC-USDT-SWAP`
- `AUDIT_LOG_PATH=var/logs/audit/events.jsonl`
- `SIGNAL_SHARED_SECRET=...` for `/signal` authentication
- `SIGNAL_IDEMPOTENCY_PATH=var/state/signal_ids.txt`
- `OKX_WS_URL=wss://ws.okx.com:8443/ws/v5/private`
- `RECONCILE_POLL_INTERVAL_SECONDS=30`

Safety defaults:
- `EXECUTION_ENABLED=false`
- `PAPER_MODE=true`
- `TRADING_HALTED=false`

## Implemented native modules

- `src/agent_trader/okx_client.py`
- `src/agent_trader/okx_account_sync.py`
- `src/agent_trader/okx_execution_service.py`
- `src/agent_trader/okx_order_service.py`
- `src/agent_trader/okx_ws.py`
- `src/agent_trader/reconcile_job.py`
- `src/agent_trader/reconcile_scheduler.py`
- `src/agent_trader/audit_log.py`
- native execution now:
  - resolves `ctVal` and converts USD notionals into OKX swap contract counts
  - reads account `posMode` and fills `posSide` when needed
  - caches leverage updates per `(inst_id, td_mode, pos_side)`
  - attaches TP/SL algo orders on OPEN trades
  - uses `reduceOnly=true` on CLOSE trades
- websocket/runtime scaffolding now:
  - builds private login + subscribe payloads for orders/positions/account
  - supports basic handler registration, ping, and reconnect skeleton
  - supports async connect/run_once/reconnect skeleton for future receive loops
  - exposes ws URL via settings for demo/live switching
- reconciliation scaffolding now:
  - immediate reconciliation after submission
  - batch reconciliation jobs for open orders
  - scheduler skeleton for periodic polling loops
- `src/agent_trader/main.py` native helpers:
  - `make_okx_client()`
  - `okx_account_state_payload()`
  - `run_okx_native_signal_pipeline()`
  - `run_primary_signal_pipeline()`
  - `process_signal_request_payload()`

## Next native steps

1. connect websocket manager to a real async transport with heartbeat + reconnect backoff loop
2. hook reconciliation scheduler to a real open-order loader and background task runner
3. add real demo-trading integration test with `OKX_FLAG=1`
4. promote from paper mode to demo mode, then tiny live size
5. enrich audit events with full proposal/risk snapshots for post-trade analytics
6. add persistent idempotency cleanup/TTL strategy for long-running deployments
