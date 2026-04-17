from agent_trader.models import AccountState, RiskLimits, StrategySignal, TradeProposal



def build_trade_proposal(
    signal: StrategySignal,
    account: AccountState,
    connector: str,
    symbol: str,
    risk_limits: RiskLimits,
    risk_fraction: float,
) -> TradeProposal:
    normalized_side = signal.side.lower()
    normalized_action = signal.position_action.upper()
    entry_price = max(signal.entry_price, 0.0)
    stop_distance = abs(signal.entry_price - signal.stop_loss_price)
    risk_budget_usd = max(account.equity_usd * max(risk_fraction, 0.0), 0.0)

    if entry_price > 0 and stop_distance > 0:
        stop_risk_ratio = stop_distance / entry_price
        desired_notional = risk_budget_usd / stop_risk_ratio
    else:
        desired_notional = risk_budget_usd

    remaining_capacity = max(risk_limits.max_notional_usd - account.current_exposure_usd, 0.0)
    if (
        risk_limits.max_notional_per_symbol_usd > 0
        and account.positions_by_symbol is not None
    ):
        existing = account.positions_by_symbol.get(symbol, 0.0)
        remaining_per_symbol = max(risk_limits.max_notional_per_symbol_usd - existing, 0.0)
        remaining_capacity = min(remaining_capacity, remaining_per_symbol)
    notional_usd = min(desired_notional, remaining_capacity)
    leverage = min(max(signal.leverage, 1.0), risk_limits.max_leverage)

    return TradeProposal(
        connector=connector,
        symbol=symbol,
        side=normalized_side,
        notional_usd=round(notional_usd, 8),
        leverage=round(leverage, 8),
        expected_slippage_bps=signal.expected_slippage_bps,
        order_type="MARKET",
        limit_price=None,
        position_action=normalized_action,
        stop_loss_price=signal.stop_loss_price,
        take_profit_price=signal.take_profit_price,
        pos_side=signal.pos_side,
    )
