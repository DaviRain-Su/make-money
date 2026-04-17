# OKX + Hummingbot + AI Agent MVP

This repo now supports two execution directions for an AI-assisted perpetual trading copilot:

- preferred current path: direct OKX native API via the `python-okx` SDK
- secondary path: Hummingbot-based execution abstraction

Core principle:
- hard risk rules approve or deny
- AI advises; AI does not bypass hard limits
- native OKX is the default execution path
- swap size uses OKX contract metadata (`ctVal`), not base-asset quantity
- paper/demo mode stays on by default

Current milestone:
- OKX chosen as first venue
- direct OKX native API path added via `python-okx`
- native OKX is now the primary path in `main.py`
- `okx_perpetual` remains available as Hummingbot connector target if needed later
- deterministic risk engine implemented and tested
- Hummingbot API client wrapper added
- account sync logic added for OKX-focused portfolio/position snapshots
- native OKX SDK wrapper and native account sync scaffold added

## What is in this repo now

- `src/agent_trader/models.py` — core domain models
- `src/agent_trader/risk.py` — deterministic hard risk checks
- `src/agent_trader/config.py` — environment-driven settings loader
- `src/agent_trader/hbot_client.py` — thin Hummingbot API wrapper for accounts/connectors/portfolio/positions
- `src/agent_trader/account_sync.py` — maps Hummingbot OKX data into local `AccountState`
- `src/agent_trader/okx_client.py` — direct OKX native SDK wrapper using `python-okx`
- `src/agent_trader/okx_account_sync.py` — maps OKX native account/position payloads into local `AccountState`
- `src/agent_trader/okx_execution_service.py` — direct OKX market-order execution helper (ctVal sizing + attachAlgoOrds SL/TP)
- `src/agent_trader/proposal_service.py` — builds `TradeProposal` from a `StrategySignal` (stop-distance sizing, exposure-remaining cap, OPEN/CLOSE intent)
- `src/agent_trader/control_state.py` — persistent halt flag (`var/state/control.json`)
- `src/agent_trader/admin_api.py` — Hermes-facing admin plane (HMAC + nonce, halt/resume/status/manual_trade, tiered confirmations)
- `src/agent_trader/signal_security.py` — shared-secret auth + idempotency for `/signal`
- `src/agent_trader/main.py` — control-plane skeleton and optional FastAPI app
- `tests/test_risk_engine.py` — risk engine tests
- `tests/test_hbot_client.py` — Hummingbot request-shape tests
- `tests/test_account_sync.py` — Hummingbot portfolio/positions mapping tests
- `tests/test_okx_client.py` — OKX SDK wrapper tests
- `tests/test_okx_account_sync.py` — OKX account/positions mapping tests
- `tests/test_okx_execution_service.py` — OKX execution tests
- `tests/test_main.py` — config and payload tests
- `docs/architecture.md` — system boundaries and flow
- `docs/okx-hummingbot-setup.md` — exchange and connector assumptions
- `prompts/` — initial AI prompt templates

## Safety model

The system is intentionally constrained:
- one exchange first: OKX
- one connector first: `okx_perpetual`
- one market first: `BTC-USDT-SWAP`
- no live credentials committed
- no live order placement yet
- every trade path (strategy `/signal` + Hermes `/admin/manual_trade`) goes through the same `evaluate_trade` hard-risk engine
- `RiskLimits.trading_halted` and a persistent `control.json` halt flag can each block all orders

## Hermes admin plane

Hermes is a separate process (not in this repo). It talks to this service over HMAC-signed HTTP, never holds OKX credentials, and cannot edit `risk.py`.

- `GET  /admin/status` — returns control state + execution flags
- `POST /admin/halt` — sets the persistent halt flag; subsequent trades are rejected with reason `trading halted`
- `POST /admin/resume` — clears the halt flag
- `POST /admin/manual_trade` — builds a `StrategySignal` from Hermes input and runs the primary pipeline (risk engine still gates the trade)

Auth: every request must include `X-Admin-Timestamp`, `X-Admin-Nonce`, and `X-Admin-Signature` headers.
Signature is `hmac_sha256(ADMIN_SHARED_SECRET, "{timestamp}.{nonce}.{path}.{canonical_json_body}")`.
Nonces are single-use (persisted at `ADMIN_NONCE_PATH`); timestamps must be within 60 seconds of server clock.

Manual-trade tiers (defaults overridable via env):
- `< ADMIN_SMALL_TRADE_USD` (500 USD) — executes on arrival
- `>= ADMIN_SMALL_TRADE_USD` — requires `confirmation: "confirmed"` in body
- `>= ADMIN_LARGE_TRADE_USD` (5000 USD) — also requires `pin` equal to `ADMIN_SHARED_SECRET`

Every admin action appends an `admin_action` event to the audit log.

## Local dashboard

A minimal read-mostly web UI is served by the same FastAPI app. Bind the app to `127.0.0.1` in production; the `/ui/*` endpoints reject non-localhost requests.

- `GET  /ui/` — single-page dashboard (status, halt button, account snapshot, audit feed)
- `GET  /ui/summary` — aggregated status + account + counters + recent events
- `GET  /ui/events?limit=N` — tail audit events as JSON
- `POST /ui/halt` / `POST /ui/resume` — flip the persistent halt flag (localhost-only; writes `admin_action` events with `source: local_ui`)

The UI is read-only for trades — placing new orders goes through `/signal` (strategy) or `/admin/manual_trade` (Hermes). The dashboard exists to show what the system itself decided (risk blocks, reconciliation mismatches, halt history), which the OKX account page does not.

## Run tests

```bash
PYTHONPATH=src python3 -m unittest -v
```

## Next build steps

1. Deploy Hummingbot separately and expose its API.
2. Add authenticated Hummingbot API client wrapper.
3. Add proposal ingestion from a simple strategy.
4. Add AI regime analysis and advisory review.
5. Add audit logging and paper-trade loop.

## First live path

Do not jump to full autonomy. Recommended order:
1. unit tests
2. local HTTP signal submission against `/signal`
3. inspect appended JSONL audit events under `AUDIT_LOG_PATH`
4. paper execution path with reconciliation fields in the response payload
5. verify websocket login/subscribe flow against `OKX_WS_URL`
6. run `run_demo_validation_workflow(...)` with OKX demo credentials
7. OKX demo mode with `OKX_FLAG=1`
8. verify order status reconciliation against OKX demo orders
9. very small OKX live size with `OKX_FLAG=0`
10. expand only after logs + risk checks are trustworthy
