import unittest

from agent_trader.okx_account_sync import sync_okx_account_state


class FakeMultiSymbolClient:
    def __init__(self, positions):
        self._positions = positions

    def get_account_balance(self, ccy="USDT"):
        return {"code": "0", "data": [{"totalEq": "5000"}]}

    def get_positions(self, inst_id=""):
        return {"code": "0", "data": self._positions}

    def get_account_bills(self, inst_type="SWAP", ccy="USDT", limit="100"):
        return {"code": "0", "data": []}


class OKXAccountSyncMultiSymbolTests(unittest.TestCase):
    def test_positions_by_symbol_aggregates_across_instruments(self):
        client = FakeMultiSymbolClient(
            [
                {"instId": "BTC-USDT-SWAP", "notionalUsd": "1000"},
                {"instId": "ETH-USDT-SWAP", "notionalUsd": "-400"},
                {"instId": "SOL-USDT-SWAP", "notionalUsd": "200"},
            ]
        )
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertEqual(state.current_exposure_usd, 1600.0)
        self.assertEqual(state.open_positions, 3)
        self.assertEqual(
            state.positions_by_symbol,
            {"BTC-USDT-SWAP": 1000.0, "ETH-USDT-SWAP": 400.0, "SOL-USDT-SWAP": 200.0},
        )

    def test_zero_notional_positions_are_skipped(self):
        client = FakeMultiSymbolClient(
            [
                {"instId": "BTC-USDT-SWAP", "notionalUsd": "1000"},
                {"instId": "ETH-USDT-SWAP", "notionalUsd": "0"},
            ]
        )
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertEqual(state.positions_by_symbol, {"BTC-USDT-SWAP": 1000.0})
        self.assertEqual(state.open_positions, 1)

    def test_symbol_scoped_returns_only_target_exposure(self):
        client = FakeMultiSymbolClient(
            [
                {"instId": "BTC-USDT-SWAP", "notionalUsd": "1000"},
                {"instId": "ETH-USDT-SWAP", "notionalUsd": "500"},
            ]
        )
        state = sync_okx_account_state(
            client=client,
            inst_id="BTC-USDT-SWAP",
            daily_pnl_pct=0.0,
            symbol_scoped=True,
        )
        self.assertEqual(state.current_exposure_usd, 1000.0)
        self.assertEqual(state.open_positions, 1)
        # positions_by_symbol still carries the full breakdown
        self.assertEqual(
            state.positions_by_symbol,
            {"BTC-USDT-SWAP": 1000.0, "ETH-USDT-SWAP": 500.0},
        )

    def test_no_positions_yields_none_positions_by_symbol(self):
        client = FakeMultiSymbolClient([])
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertIsNone(state.positions_by_symbol)
        self.assertEqual(state.current_exposure_usd, 0.0)
        self.assertEqual(state.open_positions, 0)


if __name__ == "__main__":
    unittest.main()
