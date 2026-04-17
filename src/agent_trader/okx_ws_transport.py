from dataclasses import dataclass
import json
from typing import Any, Awaitable, Callable, Optional



def _import_websockets_connect():
    from websockets import connect

    return connect



async def connect_with_websockets(url: str) -> Any:
    connect = _import_websockets_connect()
    return await connect(url)



@dataclass
class AsyncWebSocketTransport:
    url: str
    connect_fn: Callable[[str], Awaitable[Any]]
    connection: Optional[Any] = None

    async def connect(self) -> Any:
        self.connection = await self.connect_fn(self.url)
        return self.connection

    async def send(self, payload: Any) -> None:
        if self.connection is None:
            await self.connect()
        serialized = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
        await self.connection.send(serialized)

    async def recv(self) -> Any:
        if self.connection is None:
            await self.connect()
        message = await self.connection.recv()
        if isinstance(message, str):
            try:
                return json.loads(message)
            except json.JSONDecodeError:
                return message
        return message

    async def close(self) -> None:
        if self.connection is None:
            return
        await self.connection.close()
