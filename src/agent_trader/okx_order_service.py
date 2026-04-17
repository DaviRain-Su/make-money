from typing import Any, Dict



def reconcile_order_status(client: Any, inst_id: str, order_id: str) -> Dict[str, Any]:
    response = client.get_order(inst_id=inst_id, order_id=order_id)
    rows = response.get("data", []) if isinstance(response, dict) else []
    if not rows:
        return {
            "order_id": order_id,
            "symbol": inst_id,
            "status": "missing",
            "filled_size": 0.0,
            "average_fill_price": None,
        }

    row = rows[0]
    avg_px = row.get("avgPx")
    fill_sz = row.get("fillSz") or row.get("accFillSz") or 0.0
    return {
        "order_id": row.get("ordId", order_id),
        "symbol": row.get("instId", inst_id),
        "status": row.get("state", "unknown"),
        "filled_size": float(fill_sz),
        "average_fill_price": float(avg_px) if avg_px not in (None, "") else None,
        "side": row.get("side"),
    }
