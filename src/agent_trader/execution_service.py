from typing import Any, Dict, Optional

from agent_trader.models import TradeProposal



def execute_trade_proposal(
    client: Any,
    account_name: str,
    proposal: TradeProposal,
    execution_enabled: bool,
    paper_mode: bool,
    reference_price: float,
) -> Dict[str, Any]:
    base_amount = _base_amount_from_notional(proposal.notional_usd, reference_price)

    if not execution_enabled:
        return {
            "status": "disabled",
            "base_amount": base_amount,
            "connector": proposal.connector,
            "symbol": proposal.symbol,
        }

    if paper_mode:
        return {
            "status": "paper",
            "base_amount": base_amount,
            "connector": proposal.connector,
            "symbol": proposal.symbol,
            "trade_type": proposal.side.upper(),
        }

    client.set_leverage(account_name, proposal.connector, proposal.symbol, proposal.leverage)
    order = client.place_order(
        account_name=account_name,
        connector_name=proposal.connector,
        trading_pair=proposal.symbol,
        trade_type=proposal.side.upper(),
        amount=base_amount,
        order_type=proposal.order_type,
        price=proposal.limit_price,
        position_action=proposal.position_action,
    )
    result = {
        "status": order.get("status", "submitted"),
        "client_order_id": order.get("client_order_id"),
        "base_amount": base_amount,
        "connector": proposal.connector,
        "symbol": proposal.symbol,
    }
    return result



def _base_amount_from_notional(notional_usd: float, reference_price: float) -> float:
    if reference_price <= 0:
        raise ValueError("reference_price must be positive")
    return round(notional_usd / reference_price, 8)
