import unittest

from agent_trader.okx_account_sync import sync_okx_account_state


class FakeOKXClient:
    def __init__(self, balance):
        self._balance = balance

    def get_account_balance(self, ccy="USDT"):
        return self._balance

    def get_positions(self, inst_id=""):
        return {"code": "0", "data": []}

    def get_account_bills(self, inst_type="SWAP", ccy="USDT", limit="100"):
        return {"code": "0", "data": []}


class OKXAccountSyncMarginTests(unittest.TestCase):
    def test_extracts_avail_eq_mgn_ratio_imr_from_balance(self):
        client = FakeOKXClient(
            {
                "code": "0",
                "data": [
                    {
                        "totalEq": "5000",
                        "availEq": "3500",
                        "mgnRatio": "8.25",
                        "imr": "400",
                    }
                ],
            }
        )
        state = sync_okx_account_state(
            client=client,
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=0.0,
        )
        self.assertEqual(state.equity_usd, 5000.0)
        self.assertEqual(state.available_equity_usd, 3500.0)
        self.assertEqual(state.margin_ratio, 8.25)
        self.assertEqual(state.used_margin_usd, 400.0)

    def test_missing_margin_fields_become_none(self):
        client = FakeOKXClient(
            {"code": "0", "data": [{"totalEq": "1000"}]}
        )
        state = sync_okx_account_state(
            client=client,
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=0.0,
        )
        self.assertEqual(state.equity_usd, 1000.0)
        self.assertIsNone(state.available_equity_usd)
        self.assertIsNone(state.margin_ratio)
        self.assertIsNone(state.used_margin_usd)

    def test_empty_balance_response_returns_none_margin_fields(self):
        client = FakeOKXClient({"code": "0", "data": []})
        state = sync_okx_account_state(
            client=client,
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=0.0,
        )
        self.assertEqual(state.equity_usd, 0.0)
        self.assertIsNone(state.margin_ratio)


if __name__ == "__main__":
    unittest.main()
