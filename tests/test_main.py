import unittest
from unittest.mock import patch

from agent_trader.config import load_settings
from agent_trader.main import account_state_payload
from agent_trader.models import AccountState


class FakeSyncClient:
    pass


class MainModuleTests(unittest.TestCase):
    def test_load_settings_reads_hbot_account_name(self):
        with patch.dict(
            "os.environ",
            {
                "HBOT_ACCOUNT_NAME": "okx-main",
                "OKX_SYMBOL": "BTC-USDT-SWAP",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.hbot_account_name, "okx-main")
        self.assertEqual(settings.okx_symbol, "BTC-USDT-SWAP")

    def test_account_state_payload_serializes_synced_state(self):
        fake_state = AccountState(
            equity_usd=1500.0,
            daily_pnl_pct=12.5,
            current_exposure_usd=300.0,
            open_positions=1,
        )

        with patch("agent_trader.main.sync_account_state", return_value=fake_state) as mocked_sync:
            payload = account_state_payload(client=FakeSyncClient())

        self.assertEqual(
            payload,
            {
                "equity_usd": 1500.0,
                "daily_pnl_pct": 12.5,
                "current_exposure_usd": 300.0,
                "open_positions": 1,
                "account_name": "primary",
                "connector": "okx_perpetual",
                "symbol": "BTC-USDT-SWAP",
                "execution_path": "hummingbot",
            },
        )
        mocked_sync.assert_called_once()


if __name__ == "__main__":
    unittest.main()
