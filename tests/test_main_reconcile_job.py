import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import reconcile_open_orders_payload
from agent_trader.models import RiskLimits


class MainReconcileJobTests(unittest.TestCase):
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
            use_okx_native=True,
            hbot_account_name="primary",
            hbot_api_url="http://localhost:8000",
            hbot_api_username="admin",
            hbot_api_password="admin",
            execution_enabled=True,
            paper_mode=True,
            proposal_risk_fraction=0.1,
            audit_log_path="var/logs/audit/events.jsonl",
            signal_shared_secret="",
            signal_idempotency_path="var/state/signal_ids.txt",
            okx_ws_url="wss://ws.okx.com:8443/ws/v5/private",
            reconcile_poll_interval_seconds=30,
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

    def test_reconcile_open_orders_payload_uses_job(self):
        with patch("agent_trader.main.reconcile_open_orders_job", return_value=[{"status": "filled"}]) as mocked_job:
            result = reconcile_open_orders_payload(
                [{"symbol": "BTC-USDT-SWAP", "order_id": "1"}],
                client=object(),
                current_settings=self.settings,
            )
        self.assertEqual(result, {"results": [{"status": "filled"}], "count": 1, "poll_interval_seconds": 30})
        mocked_job.assert_called_once()


if __name__ == "__main__":
    unittest.main()
