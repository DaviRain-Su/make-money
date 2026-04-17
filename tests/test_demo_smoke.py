import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.demo_smoke import run_demo_smoke_test
from agent_trader.models import RiskLimits


class DemoSmokeTests(unittest.TestCase):
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
        self.payload = {
            "side": "buy",
            "confidence": 0.8,
            "entry_price": 50000,
            "stop_loss_price": 49000,
            "take_profit_price": 52000,
            "expected_slippage_bps": 5,
            "leverage": 2,
            "rationale": "demo smoke",
            "client_signal_id": "smoke-001",
        }

    def test_run_demo_smoke_test_returns_validation_summary(self):
        with patch("agent_trader.demo_smoke.run_demo_validation_workflow", return_value={"execution": {"status": "submitted", "order_id": "123"}, "risk": {"approved": True}}) as mocked_demo, \
             patch("agent_trader.demo_smoke.reconcile_open_orders_payload", return_value={"results": [{"status": "filled"}], "count": 1}) as mocked_reconcile:
            result = run_demo_smoke_test(self.payload, client=object(), current_settings=self.settings)

        self.assertEqual(result["demo_result"]["execution"]["status"], "submitted")
        self.assertEqual(result["reconciliation"]["results"][0]["status"], "filled")
        self.assertEqual(result["summary"]["order_id"], "123")
        mocked_demo.assert_called_once()
        mocked_reconcile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
