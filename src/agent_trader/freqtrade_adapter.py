"""Adapter that maps freqtrade webhook payloads onto our /signal schema.

Freqtrade emits webhooks on entry/exit events with its own field names. This
module does the minimum translation so a freqtrade instance can drive our
agent_trader execution + risk layer without changing our /signal contract.
"""

from typing import Any, Dict, Optional


_SIDE_MAP = {
    "long": "buy",
    "short": "sell",
    "buy": "buy",
    "sell": "sell",
}

_EXIT_EVENT_TYPES = {"exit", "exit_fill", "sell", "trade_exit", "close"}



def translate_freqtrade_webhook(
    body: Dict[str, Any],
    default_confidence: float = 0.7,
    default_slippage_bps: float = 8.0,
    fallback_stop_pct: float = 0.02,
    default_tp_multiple: float = 3.0,
) -> Dict[str, Any]:
    """Convert a freqtrade webhook body into our /signal request payload.

    Raises ValueError for unusable inputs (missing pair, unknown direction,
    no usable entry price). All optional fields fall back to sensible
    defaults; callers may override via the `default_*` parameters.
    """
    event_type = str(body.get("type") or body.get("event") or "").lower()

    pair = body.get("pair") or ""
    if not pair:
        raise ValueError("freqtrade payload missing pair")
    symbol = pair_to_instid(pair)

    raw_direction = str(body.get("direction") or body.get("side") or "").lower()
    side = _SIDE_MAP.get(raw_direction)
    if side is None:
        raise ValueError(f"unsupported freqtrade direction: {raw_direction!r}")

    entry_price = _first_float(body, ("open_rate", "limit", "current_rate", "close_rate"))
    if entry_price is None or entry_price <= 0:
        raise ValueError("freqtrade payload missing entry/close price")

    leverage = _safe_float(body.get("leverage"))
    if leverage is None or leverage < 1.0:
        leverage = 1.0

    # Explicit SL from freqtrade; falls back to stop_loss_pct, then a fixed pct.
    stop_loss_price = _safe_float(body.get("stop_loss"))
    if stop_loss_price is None:
        pct = _safe_float(body.get("stop_loss_pct")) or _safe_float(body.get("initial_stop_loss_pct"))
        if pct is not None:
            # freqtrade stop_loss_pct is negative for both directions (e.g. -0.05)
            distance_pct = abs(pct)
            stop_loss_price = (
                entry_price * (1.0 - distance_pct)
                if side == "buy"
                else entry_price * (1.0 + distance_pct)
            )
    if stop_loss_price is None:
        distance_pct = abs(fallback_stop_pct)
        stop_loss_price = (
            entry_price * (1.0 - distance_pct)
            if side == "buy"
            else entry_price * (1.0 + distance_pct)
        )

    take_profit_price = _safe_float(body.get("take_profit"))
    if take_profit_price is None:
        stop_distance = abs(entry_price - stop_loss_price)
        take_profit_price = (
            entry_price + default_tp_multiple * stop_distance
            if side == "buy"
            else entry_price - default_tp_multiple * stop_distance
        )

    position_action = "OPEN"
    exit_reason = body.get("exit_reason") or body.get("sell_reason")
    if event_type in _EXIT_EVENT_TYPES or exit_reason is not None:
        position_action = "CLOSE"
        # Freqtrade webhook keeps `direction` as the original trade direction
        # even on exit. Flip it so our engine submits a closing order.
        side = "sell" if side == "buy" else "buy"

    trade_id = body.get("trade_id") or body.get("id")
    if trade_id is not None:
        client_signal_id = f"freqtrade:{trade_id}:{position_action}:{symbol}:{side}"
    else:
        client_signal_id = ""

    rationale_tag = body.get("enter_tag") or exit_reason or event_type or "webhook"

    return {
        "side": side,
        "confidence": float(body.get("confidence") or default_confidence),
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "expected_slippage_bps": float(body.get("expected_slippage_bps") or default_slippage_bps),
        "leverage": leverage,
        "rationale": f"freqtrade:{rationale_tag}",
        "position_action": position_action,
        "symbol": symbol,
        "client_signal_id": client_signal_id,
    }



def pair_to_instid(pair: str) -> str:
    """Map freqtrade pair syntax to OKX instId.

    Examples:
        BTC/USDT           -> BTC-USDT-SWAP  (treated as perp)
        BTC/USDT:USDT      -> BTC-USDT-SWAP  (freqtrade futures syntax)
        BTC-USDT-SWAP      -> BTC-USDT-SWAP  (already OKX format)
    """
    raw = (pair or "").upper().strip()
    if raw.endswith("-SWAP") or raw.endswith("-PERP"):
        return raw
    core = raw.split(":")[0]
    parts = core.replace("/", "-").split("-")
    parts = [p for p in parts if p]
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]}-SWAP"
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return raw



def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def _first_float(body: Dict[str, Any], keys) -> Optional[float]:
    for key in keys:
        value = _safe_float(body.get(key))
        if value is not None:
            return value
    return None
