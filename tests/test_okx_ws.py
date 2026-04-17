import unittest

from agent_trader.okx_ws import OKXWebSocketClient, build_private_subscription_args


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)


class OKXWebSocketTests(unittest.TestCase):
    def test_build_private_subscription_args_covers_orders_positions_account(self):
        args = build_private_subscription_args(inst_type="SWAP", inst_family="BTC-USDT")
        self.assertEqual(
            args,
            [
                {"channel": "orders", "instType": "SWAP", "instFamily": "BTC-USDT"},
                {"channel": "positions", "instType": "SWAP", "instFamily": "BTC-USDT"},
                {"channel": "account"},
            ],
        )

    def test_subscribe_private_channels_sends_login_then_subscribe(self):
        ws = FakeWebSocket()
        client = OKXWebSocketClient(
            api_key="k",
            api_secret="s",
            passphrase="p",
            url="wss://ws.okx.com:8443/ws/v5/private",
            websocket=ws,
        )

        client.subscribe_private_channels(inst_type="SWAP", inst_family="BTC-USDT", timestamp="1700000000")

        self.assertEqual(ws.sent[0]["op"], "login")
        self.assertEqual(ws.sent[1]["op"], "subscribe")
        self.assertEqual(ws.sent[1]["args"][0]["channel"], "orders")


if __name__ == "__main__":
    unittest.main()
