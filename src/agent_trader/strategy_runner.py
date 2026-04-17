from dataclasses import asdict
from typing import Any, Callable, Dict, Iterable, List, Optional

from agent_trader.strategy import (
    EmaAtrConfig,
    generate_ema_atr_signal,
    parse_okx_candles,
)



def run_strategy_once(
    client: Any,
    symbols: Iterable[str],
    bar: str,
    candle_limit: int,
    strategy_config: EmaAtrConfig,
    dispatch: Callable[[Dict[str, Any]], Dict[str, Any]],
    higher_tf_bar: Optional[str] = None,
    higher_tf_candle_limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """For each symbol, fetch candles, run EMA/ATR, dispatch signal if any.

    `dispatch` takes a request payload (the same shape /signal expects) and
    returns the pipeline result. The caller supplies this so unit tests can
    inject a fake sink and production can wire it to process_signal_request_payload.

    When `strategy_config.higher_tf_slow_ema > 0` and `higher_tf_bar` is given,
    an additional candle series is fetched on that bar and passed to the signal
    generator for multi-timeframe trend confirmation.
    """
    results: List[Dict[str, Any]] = []
    want_mtf = strategy_config.higher_tf_slow_ema > 0 and higher_tf_bar
    htf_limit = str(higher_tf_candle_limit or max(strategy_config.higher_tf_slow_ema * 3, 100))
    for symbol in symbols:
        if not symbol:
            continue
        try:
            candle_resp = client.get_candles(symbol, bar=bar, limit=str(candle_limit))
        except Exception as exc:  # noqa: BLE001
            results.append({"symbol": symbol, "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}"})
            continue
        candles = parse_okx_candles(candle_resp)
        higher_tf_candles = None
        if want_mtf:
            try:
                htf_resp = client.get_candles(symbol, bar=higher_tf_bar, limit=htf_limit)
                higher_tf_candles = parse_okx_candles(htf_resp)
            except Exception as exc:  # noqa: BLE001
                results.append({"symbol": symbol, "status": "fetch_error", "error": f"higher_tf: {type(exc).__name__}: {exc}"})
                continue
        signal = generate_ema_atr_signal(symbol, candles, strategy_config, higher_tf_candles=higher_tf_candles)
        if signal is None:
            results.append({"symbol": symbol, "status": "no_signal", "bars": len(candles)})
            continue
        bar_ts = candles[-1].ts if candles else 0
        request_payload = _signal_to_request_payload(signal, bar=bar, bar_ts=bar_ts)
        try:
            dispatch_result = dispatch(request_payload)
            results.append(
                {
                    "symbol": symbol,
                    "status": "dispatched",
                    "client_signal_id": request_payload["client_signal_id"],
                    "side": signal.side,
                    "bar_ts": bar_ts,
                    "risk_approved": (dispatch_result or {}).get("risk", {}).get("approved"),
                    "execution_status": (dispatch_result or {}).get("execution", {}).get("status"),
                }
            )
        except ValueError as exc:
            # duplicate signal is not an error in the strategy runner's view
            results.append(
                {
                    "symbol": symbol,
                    "status": "duplicate" if "duplicate" in str(exc).lower() else "rejected",
                    "client_signal_id": request_payload["client_signal_id"],
                    "error": str(exc),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "symbol": symbol,
                    "status": "dispatch_error",
                    "client_signal_id": request_payload["client_signal_id"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results



def _signal_to_request_payload(signal, bar: str, bar_ts: int) -> Dict[str, Any]:
    payload = asdict(signal)
    payload["client_signal_id"] = f"ema_atr:{signal.symbol}:{bar}:{bar_ts}:{signal.side.lower()}"
    return payload
