import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import process_signal_request_payload
from agent_trader.models import RiskLimits


class MainSignalSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            environment="dev",
            okx_connector_id="okx_native",
            okx_symbol="BTC-USDT-SWAP",
            okx_api_key="k",
            okx_api_secret="s",
            okx_passphrase="p",
            okx_flag="1",
            okx_td_mode="cross",
            use_okx_native=True,
            hbot_account_name="primary",
            hbot_api_url="http://localhost:8000",
            hbot_api_username="admin",
            hbot_api_password="admin",
            execution_enabled=True,
            paper_mode=True,
            proposal_risk_fraction=0.1,
            audit_log_path=os.path.join(self.tempdir.name, "audit", "events.jsonl"),
            signal_shared_secret="topsecret",
            signal_idempotency_path=os.path.join(self.tempdir.name, "state", "signal_ids.txt"),
            control_state_path=os.path.join(self.tempdir.name, "state", "control.json"),
            admin_shared_secret="",
            admin_nonce_path=os.path.join(self.tempdir.name, "state", "admin_nonces.txt"),
            admin_small_trade_usd=500.0,
            admin_large_trade_usd=5000.0,
            okx_ws_url="wss://ws.okx.com:8443/ws/v5/private",
            reconcile_poll_interval_seconds=30,
            risk_limits=RiskLimits(
                max_notional_usd=1000.0,
                max_leverage=3.0,
                daily_loss_limit_pct=2.0,
                max_slippage_bps=15.0,
            ),
        )
        self.payload = {
            "side": "buy",
            "confidence": 0.8,
            "entry_price": 50000,
            "stop_loss_price": 49000,
            "take_profit_price": 52000,
            "expected_slippage_bps": 5,
            "leverage": 2,
            "rationale": "test",
            "client_signal_id": "sig-001",
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def test_rejects_missing_shared_secret(self):
        with self.assertRaisesRegex(PermissionError, "unauthorized"):
            process_signal_request_payload(
                self.payload,
                client=object(),
                current_settings=self.settings,
                auth_header=None,
            )

    def test_rejects_duplicate_signal_id(self):
        with patch("agent_trader.main.run_primary_signal_pipeline", return_value={"risk": {"approved": True}, "execution": {"status": "paper"}}):
            first = process_signal_request_payload(
                self.payload,
                client=object(),
                current_settings=self.settings,
                auth_header="topsecret",
            )
            self.assertEqual(first["execution"]["status"], "paper")
            with self.assertRaisesRegex(ValueError, "duplicate signal"):
                process_signal_request_payload(
                    self.payload,
                    client=object(),
                    current_settings=self.settings,
                    auth_header="topsecret",
                )


if __name__ == "__main__":
    unittest.main()
