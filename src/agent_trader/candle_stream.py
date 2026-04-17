"""End-to-end OKX public candle stream → strategy trigger.

Combines `AsyncWebSocketTransport` + `CandleStreamListener` into a minimal
long-running task: connect to the public ws, subscribe to `candle{bar}` for
a list of symbols, pump messages through the listener, and call a user
callback when each bar closes. On transport errors, back off and reconnect.

Wiring into runtime is left to the caller (`await stream.run_forever(...)`).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional

from agent_trader.okx_ws_candles import (
    CandleStreamListener,
    build_candle_subscription_args,
)
from agent_trader.strategy import Candle


PUBLIC_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"



@dataclass
class OKXCandleStream:
    transport: Any                              # AsyncWebSocketTransport or compatible
    symbols: List[str]
    bar: str = "1H"
    listener: Optional[CandleStreamListener] = None
    on_confirmed: Optional[Callable[[str, str, Candle], None]] = None
    connected: bool = False
    subscriptions_sent: bool = False
    messages_processed: int = 0
    reconnect_backoff_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.listener is None:
            handler = self.on_confirmed or (lambda _s, _b, _c: None)
            self.listener = CandleStreamListener(on_confirmed=handler)

    async def connect_and_subscribe(self) -> None:
        if not self.connected:
            await self.transport.connect()
            self.connected = True
        if not self.subscriptions_sent:
            await self.transport.send({
                "op": "subscribe",
                "args": build_candle_subscription_args(self.symbols, self.bar),
            })
            self.subscriptions_sent = True

    async def process_one(self) -> Optional[Any]:
        message = await self.transport.recv()
        if isinstance(message, dict):
            self.listener.on_message(message)
            self.messages_processed += 1
        return message

    async def run_forever(
        self,
        should_continue: Callable[[], bool],
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        while should_continue():
            try:
                await self.connect_and_subscribe()
                await self.process_one()
            except Exception:  # noqa: BLE001
                # best-effort reconnect: drop the current connection so the
                # next loop iteration reconnects from scratch.
                self.connected = False
                self.subscriptions_sent = False
                try:
                    await self.transport.close()
                except Exception:  # noqa: BLE001
                    pass
                await sleep_fn(self.reconnect_backoff_seconds)



def make_strategy_trigger(run_once_fn: Callable[[str, str], Any]) -> Callable[[str, str, Candle], None]:
    """Adapter: turn a (symbol, bar) → result function into an on_confirmed
    callback. Exceptions are swallowed — strategy errors are already surfaced
    via audit events.
    """
    def trigger(symbol: str, bar: str, _candle: Candle) -> None:
        try:
            run_once_fn(symbol, bar)
        except Exception:  # noqa: BLE001
            pass
    return trigger
