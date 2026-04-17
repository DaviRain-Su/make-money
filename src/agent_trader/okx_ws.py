import asyncio
import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


PRIVATE_WS_URL = "wss://ws.okx.com:8443/ws/v5/private"



def build_private_subscription_args(inst_type: str = "SWAP", inst_family: str = "") -> List[Dict[str, str]]:
    args = [
        {"channel": "orders", "instType": inst_type},
        {"channel": "positions", "instType": inst_type},
        {"channel": "account"},
    ]
    if inst_family:
        args[0]["instFamily"] = inst_family
        args[1]["instFamily"] = inst_family
    return args


@dataclass
class OKXWebSocketClient:
    api_key: str
    api_secret: str
    passphrase: str
    url: str = PRIVATE_WS_URL
    websocket: Optional[Any] = None

    def build_login_payload(self, timestamp: str) -> Dict[str, Any]:
        prehash = f"{timestamp}GET/users/self/verify".encode("utf-8")
        secret = self.api_secret.encode("utf-8")
        signature = base64.b64encode(hmac.new(secret, prehash, hashlib.sha256).digest()).decode("utf-8")
        return {
            "op": "login",
            "args": [
                {
                    "apiKey": self.api_key,
                    "passphrase": self.passphrase,
                    "timestamp": timestamp,
                    "sign": signature,
                }
            ],
        }

    def subscribe_private_channels(self, inst_type: str = "SWAP", inst_family: str = "", timestamp: str = "") -> None:
        if self.websocket is None:
            raise RuntimeError("websocket transport not configured")
        login_timestamp = timestamp or "0"
        self.websocket.send(self.build_login_payload(login_timestamp))
        self.websocket.send(
            {
                "op": "subscribe",
                "args": build_private_subscription_args(inst_type=inst_type, inst_family=inst_family),
            }
        )

    async def subscribe_private_channels_async(self, inst_type: str = "SWAP", inst_family: str = "", timestamp: str = "") -> None:
        if self.websocket is None:
            raise RuntimeError("websocket transport not configured")
        login_timestamp = timestamp or "0"
        await self.websocket.send(self.build_login_payload(login_timestamp))
        await self.websocket.send(
            {
                "op": "subscribe",
                "args": build_private_subscription_args(inst_type=inst_type, inst_family=inst_family),
            }
        )


@dataclass
class OKXWebSocketManager:
    client: OKXWebSocketClient
    inst_type: str = "SWAP"
    inst_family: str = ""
    connected: bool = False
    reconnect_count: int = 0
    handlers: Dict[str, Callable[[Dict[str, Any]], None]] = field(default_factory=dict)

    def register_handler(self, channel: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        self.handlers[channel] = handler

    def connect(self, timestamp: str) -> None:
        self.client.subscribe_private_channels(
            inst_type=self.inst_type,
            inst_family=self.inst_family,
            timestamp=timestamp,
        )
        self.connected = True

    async def connect_async(self, timestamp: str) -> None:
        await self.client.subscribe_private_channels_async(
            inst_type=self.inst_type,
            inst_family=self.inst_family,
            timestamp=timestamp,
        )
        self.connected = True

    def send_ping(self) -> None:
        if self.client.websocket is None:
            raise RuntimeError("websocket transport not configured")
        self.client.websocket.send("ping")

    async def send_ping_async(self) -> None:
        if self.client.websocket is None:
            raise RuntimeError("websocket transport not configured")
        await self.client.websocket.send("ping")

    def handle_message(self, message: Dict[str, Any]) -> None:
        channel = message.get("arg", {}).get("channel")
        handler = self.handlers.get(channel)
        if handler is not None:
            handler(message)

    def reconnect(self, websocket: Any, timestamp: str) -> None:
        previous = self.client.websocket
        if previous is not None and hasattr(previous, "close"):
            previous.close()
        self.client.websocket = websocket
        self.reconnect_count += 1
        self.connect(timestamp=timestamp)

    async def reconnect_async(self, websocket: Any, timestamp: str) -> None:
        previous = self.client.websocket
        if previous is not None and hasattr(previous, "close"):
            maybe = previous.close()
            if asyncio.iscoroutine(maybe):
                await maybe
        self.client.websocket = websocket
        self.reconnect_count += 1
        await self.connect_async(timestamp=timestamp)

    async def run_once(self, timestamp: str, send_ping: bool = False) -> Optional[Dict[str, Any]]:
        if not self.connected:
            await self.connect_async(timestamp=timestamp)
        if send_ping:
            await self.send_ping_async()
        if self.client.websocket is None:
            raise RuntimeError("websocket transport not configured")
        message = await self.client.websocket.recv()
        if isinstance(message, dict):
            self.handle_message(message)
            return message
        return None
