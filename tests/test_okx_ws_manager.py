import unittest

from agent_trader.okx_ws import OKXWebSocketClient, OKXWebSocketManager


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, payload):
        self.sent.append(payload)

    def close(self):
        self.closed = True


class OKXWebSocketManagerTests(unittest.TestCase):
    def test_connect_and_subscribe_sends_login_subscribe_and_ping(self):
        ws = FakeWebSocket()
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )

        manager.connect(timestamp="1700000000")
        manager.send_ping()

        self.assertEqual(ws.sent[0]["op"], "login")
        self.assertEqual(ws.sent[1]["op"], "subscribe")
        self.assertEqual(ws.sent[2], "ping")
        self.assertTrue(manager.connected)

    def test_handle_message_dispatches_to_registered_handler(self):
        ws = FakeWebSocket()
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )
        seen = []
        manager.register_handler("orders", lambda message: seen.append(message["data"][0]["ordId"]))

        manager.handle_message({"arg": {"channel": "orders"}, "data": [{"ordId": "123"}]})

        self.assertEqual(seen, ["123"])

    def test_reconnect_increments_counter_and_resubscribes(self):
        first_ws = FakeWebSocket()
        second_ws = FakeWebSocket()
        manager = OKXWebSocketManager(
            client=OKXWebSocketClient(api_key="k", api_secret="s", passphrase="p", websocket=first_ws),
            inst_type="SWAP",
            inst_family="BTC-USDT",
        )
        manager.connect(timestamp="1700000000")

        manager.reconnect(second_ws, timestamp="1700000001")

        self.assertTrue(first_ws.closed)
        self.assertEqual(manager.reconnect_count, 1)
        self.assertEqual(second_ws.sent[0]["op"], "login")
        self.assertEqual(second_ws.sent[1]["op"], "subscribe")


if __name__ == "__main__":
    unittest.main()
