import unittest

from agent_trader.account_sync import sync_account_state


class FakeHummingbotClient:
    def __init__(self, portfolio_state, positions, portfolio_history):
        self.portfolio_state = portfolio_state
        self.positions = positions
        self.portfolio_history = portfolio_history

    def get_portfolio_state(self, account_names=None, connector_names=None, refresh=False, skip_gateway=False):
        return self.portfolio_state

    def get_positions(self, account_names=None, connector_names=None, limit=50):
        return self.positions

    def get_portfolio_history(self, account_names=None, connector_names=None, limit=2, interval="1d"):
        return self.portfolio_history


class AccountSyncTests(unittest.TestCase):
    def test_sync_account_state_maps_okx_portfolio_and_positions(self):
        client = FakeHummingbotClient(
            portfolio_state={
                "okx-main": {
                    "okx_perpetual": [
                        {"asset": "USDT", "value": 1200.0},
                        {"asset": "BTC", "value": 300.0},
                    ]
                }
            },
            positions={
                "data": [
                    {
                        "account_name": "okx-main",
                        "connector_name": "okx_perpetual",
                        "trading_pair": "BTC-USDT-SWAP",
                        "notional_value": 450.0,
                    },
                    {
                        "account_name": "okx-main",
                        "connector_name": "okx_perpetual",
                        "trading_pair": "ETH-USDT-SWAP",
                        "notional_value": -150.0,
                    },
                ]
            },
            portfolio_history={
                "data": [
                    {"total_value": 1200.0},
                    {"total_value": 1500.0},
                ]
            },
        )

        state = sync_account_state(
            client=client,
            account_name="okx-main",
            connector_name="okx_perpetual",
        )

        self.assertEqual(state.equity_usd, 1500.0)
        self.assertEqual(state.current_exposure_usd, 600.0)
        self.assertEqual(state.open_positions, 2)
        self.assertAlmostEqual(state.daily_pnl_pct, 25.0)

    def test_sync_account_state_filters_to_target_symbol_when_requested(self):
        client = FakeHummingbotClient(
            portfolio_state={
                "okx-main": {
                    "okx_perpetual": [
                        {"asset": "USDT", "value": 1000.0},
                    ]
                }
            },
            positions={
                "data": [
                    {"trading_pair": "BTC-USDT-SWAP", "notional_value": 250.0},
                    {"trading_pair": "ETH-USDT-SWAP", "notional_value": 700.0},
                ]
            },
            portfolio_history={"data": []},
        )

        state = sync_account_state(
            client=client,
            account_name="okx-main",
            connector_name="okx_perpetual",
            trading_pair="BTC-USDT-SWAP",
        )

        self.assertEqual(state.current_exposure_usd, 250.0)
        self.assertEqual(state.open_positions, 1)
        self.assertEqual(state.daily_pnl_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
