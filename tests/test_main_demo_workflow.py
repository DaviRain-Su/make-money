import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import run_demo_validation_workflow
from agent_trader.models import RiskLimits


class MainDemoWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            environment="dev",
            okx_connector_id="okx_native",
            okx_symbol="BTC-USDT-SWAP",
            okx_api_key="k",
            okx_api_secret="s",
            okx_passphrase="p",
            okx_flag="1",
            okx_td_mode="cross",
            okx_ws_url="wss://ws.okx.com:8443/ws/v5/private",
            reconcile_poll_interval_seconds=30,
            use_okx_native=True,
            hbot_account_name="primary",
            hbot_api_url="http://localhost:8000",
            hbot_api_username="admin",
            hbot_api_password="admin",
            execution_enabled=True,
            paper_mode=False,
            proposal_risk_fraction=0.1,
            audit_log_path="var/logs/audit/events.jsonl",
            signal_shared_secret="",
            signal_idempotency_path="var/state/signal_ids.txt",
            control_state_path="var/state/control.json",
            admin_shared_secret="",
            admin_nonce_path="var/state/admin_nonces.txt",
            admin_small_trade_usd=500.0,
            admin_large_trade_usd=5000.0,
            risk_limits=RiskLimits(
                max_notional_usd=1000.0,
                max_leverage=3.0,
                daily_loss_limit_pct=2.0,
                max_slippage_bps=15.0,
            ),
        )

    def test_run_demo_validation_workflow_forces_demo_execution_path(self):
        with patch("agent_trader.main.process_signal_request_payload", return_value={"execution": {"status": "submitted"}}) as mocked_process:
            result = run_demo_validation_workflow(
                {
                    "side": "buy",
                    "confidence": 0.8,
                    "entry_price": 50000,
                    "stop_loss_price": 49000,
                    "take_profit_price": 52000,
                    "expected_slippage_bps": 5,
                    "leverage": 2,
                    "rationale": "demo",
                    "client_signal_id": "demo-001",
                },
                client=object(),
                current_settings=self.settings,
            )

        self.assertEqual(result["execution"]["status"], "submitted")
        passed_settings = mocked_process.call_args.kwargs["current_settings"]
        self.assertEqual(passed_settings.okx_flag, "1")
        self.assertTrue(passed_settings.execution_enabled)
        self.assertFalse(passed_settings.paper_mode)


if __name__ == "__main__":
    unittest.main()
