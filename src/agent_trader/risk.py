from typing import List

from agent_trader.models import AccountState, RiskDecision, RiskLimits, TradeProposal


ALLOWED_CONNECTORS = {"okx_perpetual", "okx_native"}
ALLOWED_SIDES = {"buy", "sell"}
ALLOWED_POSITION_ACTIONS = {"OPEN", "CLOSE"}



def evaluate_trade(proposal: TradeProposal, account: AccountState, limits: RiskLimits) -> RiskDecision:
    reasons: List[str] = []
    normalized_side = proposal.side.lower()

    if limits.trading_halted:
        reasons.append("trading halted")

    if proposal.connector not in ALLOWED_CONNECTORS:
        reasons.append("unsupported connector")

    if normalized_side not in ALLOWED_SIDES:
        reasons.append("unsupported side")

    if proposal.position_action not in ALLOWED_POSITION_ACTIONS:
        reasons.append("unsupported position action")

    if proposal.notional_usd <= 0:
        reasons.append("notional must be positive")

    if proposal.leverage < 1:
        reasons.append("leverage must be at least 1")
    elif proposal.leverage > limits.max_leverage:
        reasons.append("leverage limit exceeded")

    if proposal.expected_slippage_bps <= 0:
        reasons.append("slippage must be positive")
    elif proposal.expected_slippage_bps > limits.max_slippage_bps:
        reasons.append("slippage limit exceeded")

    if account.equity_usd <= limits.min_equity_usd:
        reasons.append("equity below minimum")

    resulting_exposure = account.current_exposure_usd + proposal.notional_usd
    if resulting_exposure > limits.max_notional_usd:
        reasons.append("notional limit exceeded")

    if account.daily_pnl_pct <= (-1 * limits.daily_loss_limit_pct):
        reasons.append("daily loss limit breached")

    return RiskDecision(approved=not reasons, reasons=reasons)
