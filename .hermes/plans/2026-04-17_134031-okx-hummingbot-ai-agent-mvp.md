# OKX + Hummingbot + AI Agent MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a first working MVP for an OKX perpetual trading copilot where Hummingbot handles execution, a local Python service handles hard risk checks, and AI supplies regime/risk judgments without direct authority to bypass limits.

**Architecture:** The system is split into three layers: Hummingbot for exchange connectivity and order execution on OKX perpetuals, a Python control plane for strategy proposals and hard risk validation, and an AI prompt layer for regime analysis / trade approval commentary. The MVP only supports one venue (OKX), one market at a time (start with BTC-USDT-SWAP), and a strict approval pipeline: strategy signal -> hard risk engine -> optional AI opinion -> execution request.

**Tech Stack:** Python 3.9+, standard library for core domain logic, FastAPI for future API service, Hummingbot API as external dependency, dotenv-style config, unittest for initial verification.

---

## Current context / assumptions

- Active workspace: `/Users/davirian/dev/active/ideas/make-money`
- Workspace is empty.
- Python 3.9.6 is installed.
- `pytest` is not installed, so initial tests should use `python3 -m unittest`.
- User explicitly chose OKX as the first exchange.
- We are creating a safe MVP scaffold, not wiring live trading credentials yet.

## MVP scope

In scope:
- Repo scaffold
- Architecture docs
- Config templates for OKX + Hummingbot
- Core domain models
- Hard risk engine that can approve/deny a proposed order
- Prompt templates for AI analyst / risk reviewer
- Minimal API skeleton for future integration

Out of scope for this first pass:
- Real Hummingbot deployment
- Live OKX credentials
- Live order placement
- Backtesting engine
- Multi-agent orchestration runtime
- Strategy alpha research

## Proposed file layout

- Create: `README.md`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `docs/architecture.md`
- Create: `docs/okx-hummingbot-setup.md`
- Create: `prompts/market_analyst.md`
- Create: `prompts/risk_manager.md`
- Create: `src/agent_trader/__init__.py`
- Create: `src/agent_trader/models.py`
- Create: `src/agent_trader/config.py`
- Create: `src/agent_trader/risk.py`
- Create: `src/agent_trader/main.py`
- Create: `tests/__init__.py`
- Create: `tests/test_risk_engine.py`

## Step-by-step plan

### Task 1: Write the failing risk-engine tests
**Objective:** Define the exact approval behavior before writing production logic.

**Files:**
- Create: `tests/test_risk_engine.py`
- Create: `tests/__init__.py`

**Step 1: Write failing test**
Cover at least:
- valid proposal is approved
- oversized position is denied
- daily drawdown breach is denied
- leverage breach is denied
- slippage breach is denied

**Step 2: Run test to verify failure**
Run: `python3 -m unittest tests.test_risk_engine -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbols.

### Task 2: Implement minimal domain models and risk engine
**Objective:** Add deterministic order/risk validation.

**Files:**
- Create: `src/agent_trader/models.py`
- Create: `src/agent_trader/risk.py`
- Modify: `tests/test_risk_engine.py`

**Step 1: Write minimal implementation**
Implement:
- `RiskLimits`
- `AccountState`
- `TradeProposal`
- `RiskDecision`
- `evaluate_trade(...)`

**Step 2: Run test to verify pass**
Run: `PYTHONPATH=src python3 -m unittest tests.test_risk_engine -v`
Expected: PASS

### Task 3: Add config + API skeleton
**Objective:** Prepare the control-plane scaffold without live integration.

**Files:**
- Create: `src/agent_trader/config.py`
- Create: `src/agent_trader/main.py`
- Create: `.env.example`
- Create: `pyproject.toml`

**Step 1: Add typed config model**
Fields should include:
- `OKX_CONNECTOR_ID`
- `OKX_SYMBOL`
- `HBOT_API_URL`
- `HBOT_API_USERNAME`
- `HBOT_API_PASSWORD`
- risk limits defaults

**Step 2: Add minimal API skeleton**
Expose:
- `/healthz`
- `/risk/check` (placeholder schema is acceptable)

### Task 4: Add docs and prompts
**Objective:** Make the system usable by future implementation work.

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/okx-hummingbot-setup.md`
- Create: `prompts/market_analyst.md`
- Create: `prompts/risk_manager.md`

**Step 1: Document architecture**
Include:
- what AI can and cannot do
- what Hummingbot owns
- what hard risk owns
- request flow

**Step 2: Document OKX setup assumptions**
Include:
- `okx_perpetual`
- single-currency margin mode
- start with BTC-USDT-SWAP paper/small size only

### Task 5: Verification pass
**Objective:** Confirm the scaffold is coherent.

**Files:**
- Review all created files

**Step 1: Run tests**
Run: `PYTHONPATH=src python3 -m unittest -v`
Expected: PASS

**Step 2: Sanity-check imports**
Run: `PYTHONPATH=src python3 -c "from agent_trader.risk import evaluate_trade; print('ok')"`
Expected: `ok`

## Risks / tradeoffs

- Hummingbot API surface may evolve; keep integration thin.
- LLM outputs are advisory only until hard constraints are enforced in code.
- Python 3.9 limits some typing niceties; avoid 3.10-only syntax.
- No live credentials should be committed.

## Next execution milestone after this scaffold

1. Deploy Hummingbot separately
2. Wire `main.py` to Hummingbot API endpoints
3. Add strategy proposal generator
4. Add AI review adapter
5. Add audit logging and paper-trade execution loop
