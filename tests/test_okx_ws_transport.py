import asyncio
import unittest

from agent_trader.okx_ws_transport import AsyncWebSocketTransport


class FakeConnection:
    def __init__(self):
        self.sent = []
        self.closed = False
        self.messages = []

    async def send(self, payload):
        self.sent.append(payload)

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        raise asyncio.CancelledError()

    async def close(self):
        self.closed = True


class AsyncWebSocketTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_uses_factory_and_allows_send_recv_close(self):
        connection = FakeConnection()
        connection.messages.append({"event": "ok"})

        async def factory(url):
            self.assertEqual(url, "wss://example")
            return connection

        transport = AsyncWebSocketTransport(url="wss://example", connect_fn=factory)
        await transport.connect()
        await transport.send({"ping": 1})
        msg = await transport.recv()
        await transport.close()

        self.assertEqual(connection.sent, [{"ping": 1}])
        self.assertEqual(msg, {"event": "ok"})
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
