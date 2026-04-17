import unittest

from agent_trader.hbot_client import HummingbotClient


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, path, json_body=None, params=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
                "params": params,
            }
        )
        return {"ok": True, "path": path}


class HummingbotClientTests(unittest.TestCase):
    def test_get_portfolio_state_posts_expected_filter_body(self):
        transport = FakeTransport()
        client = HummingbotClient(transport)

        response = client.get_portfolio_state(
            account_names=["okx-main"],
            connector_names=["okx_perpetual"],
            refresh=True,
            skip_gateway=True,
        )

        self.assertEqual(response["path"], "/portfolio/state")
        self.assertEqual(
            transport.calls[0],
            {
                "method": "POST",
                "path": "/portfolio/state",
                "json_body": {
                    "account_names": ["okx-main"],
                    "connector_names": ["okx_perpetual"],
                    "refresh": True,
                    "skip_gateway": True,
                },
                "params": None,
            },
        )

    def test_get_positions_posts_expected_filter_body(self):
        transport = FakeTransport()
        client = HummingbotClient(transport)

        response = client.get_positions(
            account_names=["okx-main"],
            connector_names=["okx_perpetual"],
            limit=25,
        )

        self.assertEqual(response["path"], "/trading/positions")
        self.assertEqual(
            transport.calls[0],
            {
                "method": "POST",
                "path": "/trading/positions",
                "json_body": {
                    "account_names": ["okx-main"],
                    "connector_names": ["okx_perpetual"],
                    "limit": 25,
                },
                "params": None,
            },
        )

    def test_get_portfolio_history_posts_expected_filter_body(self):
        transport = FakeTransport()
        client = HummingbotClient(transport)

        response = client.get_portfolio_history(
            account_names=["okx-main"],
            connector_names=["okx_perpetual"],
            limit=2,
            interval="1d",
        )

        self.assertEqual(response["path"], "/portfolio/history")
        self.assertEqual(
            transport.calls[0],
            {
                "method": "POST",
                "path": "/portfolio/history",
                "json_body": {
                    "account_names": ["okx-main"],
                    "connector_names": ["okx_perpetual"],
                    "limit": 2,
                    "interval": "1d",
                },
                "params": None,
            },
        )

    def test_set_leverage_posts_expected_body(self):
        transport = FakeTransport()
        client = HummingbotClient(transport)

        response = client.set_leverage(
            account_name="primary",
            connector_name="okx_perpetual",
            trading_pair="BTC-USDT-SWAP",
            leverage=3.0,
        )

        self.assertEqual(response["path"], "/trading/primary/okx_perpetual/leverage")
        self.assertEqual(
            transport.calls[0],
            {
                "method": "POST",
                "path": "/trading/primary/okx_perpetual/leverage",
                "json_body": {
                    "trading_pair": "BTC-USDT-SWAP",
                    "leverage": 3.0,
                },
                "params": None,
            },
        )

    def test_place_order_posts_expected_body(self):
        transport = FakeTransport()
        client = HummingbotClient(transport)

        response = client.place_order(
            account_name="primary",
            connector_name="okx_perpetual",
            trading_pair="BTC-USDT-SWAP",
            trade_type="BUY",
            amount=0.01,
            order_type="MARKET",
            position_action="OPEN",
        )

        self.assertEqual(response["path"], "/trading/orders")
        self.assertEqual(
            transport.calls[0],
            {
                "method": "POST",
                "path": "/trading/orders",
                "json_body": {
                    "account_name": "primary",
                    "connector_name": "okx_perpetual",
                    "trading_pair": "BTC-USDT-SWAP",
                    "trade_type": "BUY",
                    "amount": 0.01,
                    "order_type": "MARKET",
                    "position_action": "OPEN",
                },
                "params": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
