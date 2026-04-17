"""OKX public websocket candle stream helpers.

OKX pushes bar-by-bar candle updates on the `candle{bar}` public channel,
marking each row with `confirm="1"` when it closes. Subscribing lets the
strategy react to a new bar within a second or two instead of waiting for
the next REST poll.

This module is intentionally small:
- `build_candle_subscription_args(symbols, bar)` → the subscribe payload
- `parse_candle_push(message)` → list of (symbol, bar, Candle, confirmed)
- `CandleStreamListener` → tracks last confirmed bar per symbol and calls a
  user-supplied callback only on newly-confirmed bars, so you don't fire on
  repeated pushes of the same forming candle.

Wiring into strategy_runner is left to the caller — typically you'd register
the listener's `on_message` with an async websocket reader loop and pass a
callback that calls `run_strategy_once` for the affected symbol.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_trader.strategy import Candle


PUBLIC_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"



def build_candle_subscription_args(symbols: List[str], bar: str = "1H") -> List[Dict[str, str]]:
    channel = f"candle{bar}"
    return [{"channel": channel, "instId": sym} for sym in symbols if sym]



def parse_candle_push(message: Dict[str, Any]) -> List[Tuple[str, str, Candle, bool]]:
    """Return [(symbol, bar, Candle, confirmed)] extracted from an OKX push.

    A single push can carry multiple rows; OKX's candle channel usually sends
    one though. Returns [] for non-candle messages.
    """
    arg = message.get("arg", {}) if isinstance(message, dict) else {}
    channel = arg.get("channel", "")
    symbol = arg.get("instId", "")
    if not channel.startswith("candle") or not symbol:
        return []
    bar = channel[len("candle"):]
    rows = message.get("data", []) if isinstance(message, dict) else []
    out: List[Tuple[str, str, Candle, bool]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        confirm = str(row[8]) if len(row) > 8 else "1"
        try:
            candle = Candle(
                ts=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]) if len(row) > 5 and row[5] not in (None, "") else 0.0,
            )
        except (TypeError, ValueError):
            continue
        out.append((symbol, bar, candle, confirm == "1"))
    return out



@dataclass
class CandleStreamListener:
    on_confirmed: Callable[[str, str, Candle], None]
    last_confirmed_ts: Dict[Tuple[str, str], int] = field(default_factory=dict)

    def on_message(self, message: Dict[str, Any]) -> None:
        for symbol, bar, candle, confirmed in parse_candle_push(message):
            if not confirmed:
                continue
            key = (symbol, bar)
            prior = self.last_confirmed_ts.get(key)
            if prior is not None and candle.ts <= prior:
                # duplicate / stale confirmed push, ignore
                continue
            self.last_confirmed_ts[key] = candle.ts
            try:
                self.on_confirmed(symbol, bar, candle)
            except Exception:  # noqa: BLE001
                # never let a bad handler kill the loop; caller's own
                # strategy dispatch already writes audit events on failure
                pass
