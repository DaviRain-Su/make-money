import unittest

from agent_trader.okx_account_sync import sync_okx_account_state


class FakeClient:
    def __init__(self, positions):
        self._positions = positions

    def get_account_balance(self, ccy="USDT"):
        return {"code": "0", "data": [{"totalEq": "10000"}]}

    def get_positions(self, inst_id=""):
        return {"code": "0", "data": self._positions}

    def get_account_bills(self, inst_type="SWAP", ccy="USDT", limit="100"):
        return {"code": "0", "data": []}


class OKXAccountSyncPositionsDetailTests(unittest.TestCase):
    def test_extracts_mark_liq_distance_and_side(self):
        client = FakeClient(
            [
                {
                    "instId": "BTC-USDT-SWAP",
                    "notionalUsd": "1000",
                    "markPx": "50000",
                    "liqPx": "45000",
                    "posSide": "long",
                },
                {
                    "instId": "ETH-USDT-SWAP",
                    "notionalUsd": "500",
                    "markPx": "3000",
                    "liqPx": "3300",
                    "posSide": "short",
                },
            ]
        )
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        detail = state.positions_detail
        self.assertIsNotNone(detail)
        btc = detail["BTC-USDT-SWAP"]
        self.assertEqual(btc["side"], "long")
        self.assertEqual(btc["mark_px"], 50000.0)
        self.assertEqual(btc["liq_px"], 45000.0)
        self.assertAlmostEqual(btc["distance_pct"], 0.1)
        eth = detail["ETH-USDT-SWAP"]
        self.assertEqual(eth["side"], "short")
        self.assertAlmostEqual(eth["distance_pct"], 0.1)

    def test_position_without_liq_price_has_null_distance(self):
        client = FakeClient(
            [
                {
                    "instId": "BTC-USDT-SWAP",
                    "notionalUsd": "1000",
                    "markPx": "50000",
                    "liqPx": "",
                    "posSide": "long",
                },
            ]
        )
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertIsNone(state.positions_detail["BTC-USDT-SWAP"]["distance_pct"])

    def test_side_inferred_from_pos_when_pos_side_blank(self):
        client = FakeClient(
            [
                {
                    "instId": "SOL-USDT-SWAP",
                    "notionalUsd": "200",
                    "markPx": "100",
                    "liqPx": "90",
                    "posSide": "",
                    "pos": "-5",
                },
            ]
        )
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertEqual(state.positions_detail["SOL-USDT-SWAP"]["side"], "short")

    def test_no_positions_yields_none_detail(self):
        client = FakeClient([])
        state = sync_okx_account_state(client=client, daily_pnl_pct=0.0)
        self.assertIsNone(state.positions_detail)


if __name__ == "__main__":
    unittest.main()
