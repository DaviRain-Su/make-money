from typing import Any, Dict, Iterable, List, Optional

from agent_trader.models import AccountState



def sync_account_state(
    client: Any,
    account_name: str,
    connector_name: str,
    trading_pair: Optional[str] = None,
) -> AccountState:
    portfolio_state = client.get_portfolio_state(
        account_names=[account_name],
        connector_names=[connector_name],
        refresh=True,
        skip_gateway=True,
    )
    positions_response = client.get_positions(
        account_names=[account_name],
        connector_names=[connector_name],
        limit=50,
    )
    portfolio_history = client.get_portfolio_history(
        account_names=[account_name],
        connector_names=[connector_name],
        limit=2,
        interval="1d",
    )

    equity_usd = _extract_equity_usd(portfolio_state, account_name, connector_name)
    positions = _extract_positions(positions_response)
    filtered_positions = _filter_positions(positions, connector_name, trading_pair)
    current_exposure_usd = sum(abs(_position_notional_usd(position)) for position in filtered_positions)
    open_positions = len(filtered_positions)
    daily_pnl_pct = _extract_daily_pnl_pct(portfolio_history, equity_usd)

    return AccountState(
        equity_usd=equity_usd,
        daily_pnl_pct=daily_pnl_pct,
        current_exposure_usd=current_exposure_usd,
        open_positions=open_positions,
    )



def _extract_equity_usd(portfolio_state: Dict[str, Any], account_name: str, connector_name: str) -> float:
    account_bucket = portfolio_state.get(account_name, {})
    connector_bucket = account_bucket.get(connector_name, [])
    total_value = 0.0
    for item in connector_bucket:
        value = item.get("value")
        if value is not None:
            total_value += float(value)
    return total_value



def _extract_positions(positions_response: Any) -> List[Dict[str, Any]]:
    if isinstance(positions_response, list):
        return positions_response
    if isinstance(positions_response, dict):
        data = positions_response.get("data", [])
        if isinstance(data, list):
            return data
    return []



def _filter_positions(
    positions: Iterable[Dict[str, Any]],
    connector_name: str,
    trading_pair: Optional[str],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for position in positions:
        position_connector = position.get("connector_name")
        if position_connector not in (None, connector_name):
            continue
        pair = position.get("trading_pair")
        if trading_pair is not None and pair != trading_pair:
            continue
        if _position_notional_usd(position) == 0:
            continue
        filtered.append(position)
    return filtered



def _position_notional_usd(position: Dict[str, Any]) -> float:
    for key in ("notional_value", "notional_usd", "position_value", "value"):
        value = position.get(key)
        if value is not None:
            return float(value)
    amount = position.get("amount") or position.get("size")
    mark_price = position.get("mark_price") or position.get("entry_price") or position.get("price")
    if amount is not None and mark_price is not None:
        return float(amount) * float(mark_price)
    return 0.0



def _extract_daily_pnl_pct(portfolio_history: Any, current_equity_usd: float) -> float:
    history_rows = portfolio_history.get("data", []) if isinstance(portfolio_history, dict) else []
    if len(history_rows) < 2:
        return 0.0
    baseline = _history_total_value(history_rows[0])
    latest = _history_total_value(history_rows[-1])
    reference = latest if current_equity_usd == 0 else current_equity_usd
    if baseline <= 0 or reference <= 0:
        return 0.0
    return ((reference - baseline) / baseline) * 100.0



def _history_total_value(row: Dict[str, Any]) -> float:
    value = row.get("total_value")
    if value is not None:
        return float(value)
    balances = row.get("balances", [])
    if isinstance(balances, list):
        return sum(float(item.get("value", 0.0)) for item in balances)
    return 0.0
