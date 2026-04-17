import unittest

from agent_trader.okx_account_sync import sync_okx_account_state


class FakeOKXClient:
    def get_account_balance(self, ccy='USDT'):
        return {
            "code": "0",
            "data": [
                {
                    "totalEq": "1500",
                    "details": [
                        {"ccy": "USDT", "eqUsd": "1200"},
                        {"ccy": "BTC", "eqUsd": "300"},
                    ],
                }
            ],
        }

    def get_positions(self, inst_id=''):
        return {
            "code": "0",
            "data": [
                {"instId": "BTC-USDT-SWAP", "notionalUsd": "450"},
                {"instId": "ETH-USDT-SWAP", "notionalUsd": "-150"},
            ],
        }

    def get_account_bills(self, inst_type='SWAP', ccy='USDT', limit='100'):
        return {
            "code": "0",
            "data": [
                {"subType": "173", "pnl": "25"},
                {"subType": "173", "pnl": "-5"},
            ],
        }


class OKXAccountSyncTests(unittest.TestCase):
    def test_sync_okx_account_state_maps_balance_and_positions(self):
        state = sync_okx_account_state(
            client=FakeOKXClient(),
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=1.25,
            symbol_scoped=False,
        )
        self.assertEqual(state.equity_usd, 1500.0)
        self.assertEqual(state.current_exposure_usd, 600.0)
        self.assertEqual(state.open_positions, 2)
        self.assertEqual(state.daily_pnl_pct, 1.25)

    def test_sync_okx_account_state_can_scope_to_single_symbol(self):
        state = sync_okx_account_state(
            client=FakeOKXClient(),
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=0.0,
            symbol_scoped=True,
        )
        self.assertEqual(state.equity_usd, 1500.0)
        self.assertEqual(state.current_exposure_usd, 450.0)
        self.assertEqual(state.open_positions, 1)

    def test_sync_okx_account_state_can_compute_daily_pnl_pct_from_bills(self):
        state = sync_okx_account_state(
            client=FakeOKXClient(),
            inst_id="BTC-USDT-SWAP",
            ccy="USDT",
            daily_pnl_pct=None,
            symbol_scoped=True,
        )
        self.assertAlmostEqual(state.daily_pnl_pct, (20.0 / 1500.0) * 100.0)


if __name__ == "__main__":
    unittest.main()
