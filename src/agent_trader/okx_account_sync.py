from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_trader.models import AccountState



def sync_okx_account_state(
    client: Any,
    inst_id: str = "",
    ccy: str = "USDT",
    daily_pnl_pct: Optional[float] = 0.0,
    symbol_scoped: bool = False,
) -> AccountState:
    """Pull account balance + all SWAP positions, and map into AccountState.

    - Always returns `positions_by_symbol` with the per-instId breakdown so
      risk engine can enforce per-symbol limits.
    - `current_exposure_usd` is account-wide by default. When
      `symbol_scoped=True` and `inst_id` is provided, it falls back to just
      that single symbol's exposure (legacy single-symbol behaviour).
    """
    balance_response = client.get_account_balance(ccy=ccy)
    positions_response = client.get_positions("")

    equity_usd = _extract_total_equity(balance_response)
    positions = _extract_positions(positions_response)

    positions_by_symbol: Dict[str, float] = {}
    positions_detail: Dict[str, Dict[str, Any]] = {}
    for position in positions:
        symbol = position.get("instId")
        if not symbol:
            continue
        notional = abs(_extract_notional_usd(position))
        if notional <= 0:
            continue
        positions_by_symbol[symbol] = positions_by_symbol.get(symbol, 0.0) + notional
        detail = _build_position_detail(position, notional)
        if detail:
            # If multiple rows for the same instId (shouldn't happen in net mode,
            # can happen in long_short mode), keep the one with smallest distance
            # (most dangerous) for the guard check.
            prior = positions_detail.get(symbol)
            if prior is None or _is_closer_to_liq(detail, prior):
                positions_detail[symbol] = detail

    if symbol_scoped and inst_id:
        current_exposure_usd = positions_by_symbol.get(inst_id, 0.0)
        open_positions = 1 if current_exposure_usd > 0 else 0
    else:
        current_exposure_usd = sum(positions_by_symbol.values())
        open_positions = len(positions_by_symbol)

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
        positions_by_symbol=positions_by_symbol or None,
        positions_detail=positions_detail or None,
    )



def _build_position_detail(position: Dict[str, Any], notional_usd: float) -> Optional[Dict[str, Any]]:
    mark_px = _safe_float(position.get("markPx"))
    liq_px = _safe_float(position.get("liqPx"))
    pos_side = (position.get("posSide") or "").lower() or None
    pos_value = _safe_float(position.get("pos"))
    inferred_side: Optional[str]
    if pos_side in {"long", "short"}:
        inferred_side = pos_side
    elif pos_value is not None and pos_value != 0:
        inferred_side = "long" if pos_value > 0 else "short"
    else:
        inferred_side = None

    distance_pct: Optional[float] = None
    if mark_px is not None and liq_px is not None and mark_px > 0 and liq_px > 0:
        distance_pct = abs(mark_px - liq_px) / mark_px

    return {
        "notional_usd": notional_usd,
        "mark_px": mark_px,
        "liq_px": liq_px,
        "distance_pct": distance_pct,
        "side": inferred_side,
    }



def _is_closer_to_liq(candidate: Dict[str, Any], existing: Dict[str, Any]) -> bool:
    c = candidate.get("distance_pct")
    e = existing.get("distance_pct")
    if c is None:
        return False
    if e is None:
        return True
    return c < e



def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



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
