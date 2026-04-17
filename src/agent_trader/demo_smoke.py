from typing import Any, Dict, Optional

from agent_trader.main import reconcile_open_orders_payload, run_demo_validation_workflow



def run_demo_smoke_test(
    payload: Dict[str, Any],
    client: Optional[Any] = None,
    current_settings: Optional[Any] = None,
) -> Dict[str, Any]:
    demo_result = run_demo_validation_workflow(payload, client=client, current_settings=current_settings)
    order_id = demo_result.get("execution", {}).get("order_id")
    symbol = payload.get("symbol") or getattr(current_settings, "okx_symbol", None) or demo_result.get("execution", {}).get("symbol")
    reconciliation = {"results": [], "count": 0}
    if order_id and symbol:
        reconciliation = reconcile_open_orders_payload(
            [{"symbol": symbol, "order_id": order_id}],
            client=client,
            current_settings=current_settings,
        )
    return {
        "demo_result": demo_result,
        "reconciliation": reconciliation,
        "summary": {
            "risk_approved": demo_result.get("risk", {}).get("approved"),
            "execution_status": demo_result.get("execution", {}).get("status"),
            "order_id": order_id,
        },
    }
