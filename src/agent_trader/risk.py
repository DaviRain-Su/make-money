from typing import Iterable, List, Optional, Set

from agent_trader.models import AccountState, RiskDecision, RiskLimits, TradeProposal


ALLOWED_CONNECTORS = {"okx_perpetual", "okx_native"}
ALLOWED_SIDES = {"buy", "sell"}
ALLOWED_POSITION_ACTIONS = {"OPEN", "CLOSE"}



def evaluate_trade(
    proposal: TradeProposal,
    account: AccountState,
    limits: RiskLimits,
    allowed_symbols: Optional[Iterable[str]] = None,
) -> RiskDecision:
    reasons: List[str] = []
    normalized_side = proposal.side.lower()
    allowlist: Optional[Set[str]] = None
    if allowed_symbols is not None:
        allowlist = {token for token in allowed_symbols if token}

    if limits.trading_halted:
        reasons.append("trading halted")

    if proposal.connector not in ALLOWED_CONNECTORS:
        reasons.append("unsupported connector")

    if normalized_side not in ALLOWED_SIDES:
        reasons.append("unsupported side")

    if proposal.position_action not in ALLOWED_POSITION_ACTIONS:
        reasons.append("unsupported position action")

    if not proposal.symbol:
        reasons.append("symbol required")
    elif allowlist and proposal.symbol not in allowlist:
        reasons.append("symbol not in allowed list")

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

    # Per-symbol notional cap. Skips when we don't know the breakdown, or the
    # limit is disabled (=0).
    if (
        limits.max_notional_per_symbol_usd > 0
        and proposal.notional_usd > 0
        and proposal.symbol
        and account.positions_by_symbol is not None
    ):
        existing = account.positions_by_symbol.get(proposal.symbol, 0.0)
        projected = existing + proposal.notional_usd
        if projected > limits.max_notional_per_symbol_usd:
            reasons.append("per-symbol notional limit exceeded")

    # Max concurrent open positions. Only applies to OPEN actions on brand-new
    # symbols; adding to an existing position (or closing) always allowed.
    if (
        limits.max_open_positions > 0
        and proposal.position_action == "OPEN"
        and account.positions_by_symbol is not None
        and len(account.positions_by_symbol) >= limits.max_open_positions
        and (proposal.symbol or "") not in account.positions_by_symbol
    ):
        reasons.append("too many open positions")

    # Liquidation-distance guard. If any position sits too close to its
    # liquidation price, block new opens to avoid piling risk on a fragile book.
    if (
        limits.min_liquidation_distance_pct > 0
        and proposal.position_action == "OPEN"
        and account.positions_detail
    ):
        for sym, detail in account.positions_detail.items():
            distance = detail.get("distance_pct") if isinstance(detail, dict) else None
            if distance is None:
                continue
            if distance < limits.min_liquidation_distance_pct:
                reasons.append("position near liquidation")
                break

    # Margin-aware checks. All guarded on "is this value known?" so paths that
    # don't yet supply margin info (Hummingbot sync) skip them silently.
    if (
        limits.min_available_equity_usd > 0
        and account.available_equity_usd is not None
        and account.available_equity_usd < limits.min_available_equity_usd
    ):
        reasons.append("available equity below minimum")

    if (
        limits.min_margin_ratio > 0
        and account.margin_ratio is not None
        and account.margin_ratio < limits.min_margin_ratio
    ):
        reasons.append("margin ratio below safety threshold")

    if proposal.notional_usd > 0 and proposal.leverage >= 1 and account.equity_usd > 0:
        projected_initial_margin = proposal.notional_usd / proposal.leverage
        baseline_used = account.used_margin_usd if account.used_margin_usd is not None else 0.0
        projected_used = baseline_used + projected_initial_margin
        utilization = projected_used / account.equity_usd
        if utilization > limits.max_margin_utilization:
            reasons.append("margin utilization exceeds cap")

        if (
            account.available_equity_usd is not None
            and projected_initial_margin > account.available_equity_usd
        ):
            reasons.append("insufficient available margin for new position")

    return RiskDecision(approved=not reasons, reasons=reasons)
