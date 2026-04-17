import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.healthcheck import run_local_healthcheck
from agent_trader.models import RiskLimits


class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            environment="dev",
            okx_connector_id="okx_native",
            okx_symbol="BTC-USDT-SWAP",
            okx_api_key="k",
            okx_api_secret="s",
            okx_passphrase="p",
            okx_flag="0",
            okx_td_mode="cross",
            okx_ws_url="wss://ws.okx.com:8443/ws/v5/private",
            reconcile_poll_interval_seconds=30,
            use_okx_native=True,
            hbot_account_name="primary",
            hbot_api_url="http://localhost:8000",
            hbot_api_username="admin",
            hbot_api_password="admin",
            execution_enabled=False,
            paper_mode=True,
            proposal_risk_fraction=0.03,
            audit_log_path="var/logs/audit/events.jsonl",
            signal_shared_secret="secret",
            signal_idempotency_path="var/state/signal_ids.txt",
            control_state_path="var/state/control.json",
            admin_shared_secret="admin-secret",
            admin_nonce_path="var/state/admin_nonces.txt",
            admin_small_trade_usd=500.0,
            admin_large_trade_usd=5000.0,
            risk_limits=RiskLimits(
                max_notional_usd=1000.0,
                max_leverage=3.0,
                daily_loss_limit_pct=2.0,
                max_slippage_bps=15.0,
                min_equity_usd=25.0,
            ),
        )

    def test_run_local_healthcheck_combines_account_reconcile_and_runtime(self):
        fake_daemon = type("FakeDaemon", (), {"run_once": lambda self, send_ping=False: None, "last_error": None})()
        with patch("agent_trader.healthcheck.okx_account_state_payload", return_value={"equity_usd": 34.0}), \
             patch("agent_trader.healthcheck.reconcile_open_orders_payload", return_value={"results": [], "count": 0, "poll_interval_seconds": 30}), \
             patch("agent_trader.healthcheck.build_runtime_daemon", return_value=fake_daemon):
            result = run_local_healthcheck(current_settings=self.settings)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["account"]["equity_usd"], 34.0)
        self.assertEqual(result["reconciliation"]["count"], 0)
        self.assertEqual(result["runtime"]["status"], "ok")
        self.assertEqual(result["settings"]["okx_flag"], "0")

    def test_run_local_healthcheck_reports_runtime_failure(self):
        fake_daemon = type("FakeDaemon", (), {"run_once": lambda self, send_ping=False: None, "last_error": "ws boom"})()
        with patch("agent_trader.healthcheck.okx_account_state_payload", return_value={"equity_usd": 34.0}), \
             patch("agent_trader.healthcheck.reconcile_open_orders_payload", return_value={"results": [], "count": 0, "poll_interval_seconds": 30}), \
             patch("agent_trader.healthcheck.build_runtime_daemon", return_value=fake_daemon):
            result = run_local_healthcheck(current_settings=self.settings)

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["runtime"]["status"], "error")
        self.assertEqual(result["runtime"]["error"], "ws boom")


if __name__ == "__main__":
    unittest.main()
