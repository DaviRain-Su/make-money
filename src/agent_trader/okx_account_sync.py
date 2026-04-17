from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_trader.models import AccountState



def sync_okx_account_state(
    client: Any,
    inst_id: str,
    ccy: str = "USDT",
    daily_pnl_pct: Optional[float] = 0.0,
    symbol_scoped: bool = True,
) -> AccountState:
    balance_response = client.get_account_balance(ccy=ccy)
    positions_response = client.get_positions(inst_id if symbol_scoped else "")

    equity_usd = _extract_total_equity(balance_response)
    positions = _extract_positions(positions_response)
    if symbol_scoped:
        positions = [position for position in positions if position.get("instId") == inst_id]
    current_exposure_usd = sum(abs(_extract_notional_usd(position)) for position in positions)
    open_positions = len([position for position in positions if _extract_notional_usd(position) != 0.0])

    resolved_daily_pnl_pct = daily_pnl_pct
    if resolved_daily_pnl_pct is None:
        bills_response = client.get_account_bills(inst_type="SWAP", ccy=ccy, limit="100")
        resolved_daily_pnl_pct = _extract_daily_pnl_pct_from_bills(bills_response, equity_usd)

    available_equity_usd = _extract_account_float(balance_response, "availEq")
    margin_ratio = _extract_account_float(balance_response, "mgnRatio")
    used_margin_usd = _extract_account_float(balance_response, "imr")

    return AccountState(
        equity_usd=equity_usd,
        daily_pnl_pct=resolved_daily_pnl_pct,
        current_exposure_usd=current_exposure_usd,
        open_positions=open_positions,
        available_equity_usd=available_equity_usd,
        margin_ratio=margin_ratio,
        used_margin_usd=used_margin_usd,
    )



def _extract_account_float(balance_response: Dict[str, Any], key: str) -> Optional[float]:
    rows = balance_response.get("data", []) if isinstance(balance_response, dict) else []
    if not rows:
        return None
    value = rows[0].get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def _extract_total_equity(balance_response: Dict[str, Any]) -> float:
    rows = balance_response.get("data", [])
    if not rows:
        return 0.0
    total_eq = rows[0].get("totalEq")
    if total_eq not in (None, ""):
        return float(total_eq)
    details = rows[0].get("details", [])
    return sum(float(item.get("eqUsd", 0.0)) for item in details)



def _extract_positions(positions_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = positions_response.get("data", [])
    return data if isinstance(data, list) else []



def _extract_notional_usd(position: Dict[str, Any]) -> float:
    for key in ("notionalUsd", "notionalUSD", "notional_value"):
        value = position.get(key)
        if value not in (None, ""):
            return float(value)
    pos = position.get("pos")
    mark_px = position.get("markPx") or position.get("last")
    if pos not in (None, "") and mark_px not in (None, ""):
        return float(pos) * float(mark_px)
    return 0.0



def _extract_daily_pnl_pct_from_bills(bills_response: Dict[str, Any], equity_usd: float) -> float:
    if equity_usd <= 0:
        return 0.0
    rows = bills_response.get("data", [])
    realized_pnl = 0.0
    day_start_ms = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    for row in rows:
        ts = row.get("ts")
        if ts not in (None, "") and int(ts) < day_start_ms:
            continue
        pnl = row.get("pnl")
        if pnl in (None, ""):
            continue
        realized_pnl += float(pnl)
    return (realized_pnl / equity_usd) * 100.0
