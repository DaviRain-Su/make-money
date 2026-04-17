import asyncio
import unittest

from agent_trader.okx_ws import OKXWebSocketClient, OKXWebSocketManager


class FakeAsyncWebSocket:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.sent = []
        self.closed = False

    async def send(self, payload):
        self.sent.append(payload)

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        raise asyncio.CancelledError()

    async def close(self):
        self.closed = True


class OKXWebSocketRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_dispatches_received_message(self):
        ws = FakeAsyncWebSocket([
            {"arg": {"channel": "orders"}, "data": [{"ordId": "123"}]}
        ])
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )
        seen = []
        manager.register_handler("orders", lambda message: seen.append(message["data"][0]["ordId"]))

        await manager.run_once(timestamp="1700000000")

        self.assertEqual(seen, ["123"])
        self.assertEqual(ws.sent[0]["op"], "login")
        self.assertEqual(ws.sent[1]["op"], "subscribe")

    async def test_run_once_sends_ping_before_receive(self):
        ws = FakeAsyncWebSocket([
            {"arg": {"channel": "account"}, "data": [{"eq": "1000"}]}
        ])
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )

        await manager.run_once(timestamp="1700000000", send_ping=True)

        self.assertEqual(ws.sent[2], "ping")

    async def test_reconnect_async_replaces_transport_and_resubscribes(self):
        first_ws = FakeAsyncWebSocket()
        second_ws = FakeAsyncWebSocket()
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=first_ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )

        await manager.connect_async(timestamp="1700000000")
        await manager.reconnect_async(second_ws, timestamp="1700000001")

        self.assertTrue(first_ws.closed)
        self.assertEqual(manager.reconnect_count, 1)
        self.assertEqual(second_ws.sent[0]["op"], "login")
        self.assertEqual(second_ws.sent[1]["op"], "subscribe")


if __name__ == "__main__":
    unittest.main()
