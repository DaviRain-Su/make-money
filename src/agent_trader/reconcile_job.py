from typing import Any, Dict, List

from agent_trader.audit_log import append_audit_event
from agent_trader.okx_order_service import reconcile_order_status



def reconcile_open_orders_job(
    client: Any,
    open_orders: List[Dict[str, str]],
    audit_log_path: str,
    execution_path: str = "okx_native",
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for order in open_orders:
        symbol = order["symbol"]
        order_id = order["order_id"]
        result = reconcile_order_status(client, symbol, order_id)
        append_audit_event(
            audit_log_path,
            {
                "event_type": "order_reconciled",
                "execution_path": execution_path,
                "symbol": symbol,
                "order_id": order_id,
                "reconciliation_status": result.get("status"),
                "filled_size": result.get("filled_size"),
            },
        )
        results.append(result)
    return results
