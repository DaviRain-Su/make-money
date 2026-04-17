# Architecture

## Objective

Build an AI-assisted OKX perpetual trading copilot with strict execution boundaries.

## System boundary

1. Hummingbot owns
- OKX connectivity
- exchange-specific order translation
- order lifecycle management
- position synchronization
- eventual execution calls

2. Hard risk layer owns
- max notional checks
- leverage cap checks
- daily drawdown stop
- slippage cap checks
- unsupported connector / malformed proposal rejection

3. AI layer owns
- market regime classification
- qualitative trade commentary
- confidence / caution scoring
- suggestion to pause or reduce trade frequency

4. AI layer explicitly does not own
- bypassing risk limits
- changing leverage cap without code/config change
- forcing order placement after denial
- disabling kill switch logic

## MVP request flow

1. Strategy or operator creates `TradeProposal`
2. Control plane loads `AccountState`
3. `evaluate_trade(...)` returns `RiskDecision`
4. If denied, trade stops and denial is logged
5. If approved, optional AI commentary can be attached
6. Approved request is sent to Hummingbot API for execution in a later phase

## Design choice: AI is advisory, not sovereign

This is deliberate. LLMs are good at synthesis and context, but poor as final guardians of capital. The code therefore treats AI output as advisory metadata unless and until a future, separately reviewed workflow permits limited autonomy.

## Initial market scope

- Venue: OKX
- Connector: `okx_perpetual`
- Symbol: `BTC-USDT-SWAP`
- Position style: start one-way, one symbol, small size only

## Current implemented services

- `hbot_client.py` — authenticated Hummingbot API wrapper
- `account_sync.py` — account and exposure snapshot fetcher

## Target services for next phase

- `proposal_service.py` — transforms strategy output into `TradeProposal`
- `audit_log.py` — append-only decision and execution log
- `ai_review.py` — prompt adapter and structured advisory response
- `execution_service.py` — sends approved orders to Hummingbot trading endpoints
