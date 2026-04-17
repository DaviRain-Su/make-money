from typing import Any, Dict, List, Optional

from agent_trader.models import TradeProposal
from agent_trader.okx_order_service import reconcile_order_status



def execute_okx_trade_proposal(
    client: Any,
    proposal: TradeProposal,
    execution_enabled: bool,
    paper_mode: bool,
    reference_price: float,
) -> Dict[str, Any]:
    contract_value = client.get_contract_value(proposal.symbol)
    size = _contract_size_from_notional(proposal.notional_usd, reference_price, contract_value)
    attach_algo_ords = _build_attach_algo_ords(proposal)

    if not execution_enabled:
        return {
            "status": "disabled",
            "symbol": proposal.symbol,
            "size": size,
            "contract_value": contract_value,
        }

    if paper_mode:
        return {
            "status": "paper",
            "symbol": proposal.symbol,
            "size": size,
            "side": proposal.side,
            "contract_value": contract_value,
            "position_action": proposal.position_action,
            "attach_algo_ords": attach_algo_ords,
        }

    response = client.place_market_order(
        inst_id=proposal.symbol,
        side=proposal.side,
        size=size,
        leverage=proposal.leverage,
        reduce_only=proposal.position_action == "CLOSE",
        pos_side=proposal.pos_side,
        attach_algo_ords=attach_algo_ords,
    )
    data = response.get("data", []) if isinstance(response, dict) else []
    order_id = data[0].get("ordId") if data else None
    result = {
        "status": "submitted",
        "symbol": proposal.symbol,
        "size": size,
        "order_id": order_id,
        "contract_value": contract_value,
        "position_action": proposal.position_action,
    }
    if order_id is not None:
        result["reconciliation"] = reconcile_order_status(client, proposal.symbol, order_id)
    return result



def _contract_size_from_notional(notional_usd: float, reference_price: float, contract_value: float) -> str:
    if reference_price <= 0:
        raise ValueError("reference_price must be positive")
    if contract_value <= 0:
        raise ValueError("contract_value must be positive")
    contracts = round(notional_usd / (reference_price * contract_value))
    if contracts <= 0:
        contracts = 1
    return str(int(contracts))



def _build_attach_algo_ords(proposal: TradeProposal) -> Optional[List[Dict[str, str]]]:
    if proposal.position_action == "CLOSE":
        return None

    algo: Dict[str, str] = {}
    if proposal.take_profit_price is not None:
        algo["tpTriggerPx"] = str(proposal.take_profit_price)
        algo["tpOrdPx"] = "-1"
    if proposal.stop_loss_price is not None:
        algo["slTriggerPx"] = str(proposal.stop_loss_price)
        algo["slOrdPx"] = "-1"
    if not algo:
        return None
    return [algo]
