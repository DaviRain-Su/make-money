import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.runtime_entry import build_runtime_daemon
from agent_trader.models import RiskLimits


class RuntimeEntryTests(unittest.TestCase):
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

    def test_build_runtime_daemon_wires_transport_manager_scheduler_and_daemon(self):
        fake_ws_client = type("WsClient", (), {"url": "wss://ws.okx.com:8443/ws/v5/private"})()
        with patch("agent_trader.runtime_entry.make_okx_ws_client", return_value=fake_ws_client) as mocked_client, \
             patch("agent_trader.runtime_entry.AsyncWebSocketTransport", return_value="transport") as mocked_transport, \
             patch("agent_trader.runtime_entry.OKXWebSocketManager", return_value="manager") as mocked_manager, \
             patch("agent_trader.runtime_entry.ReconcileScheduler", return_value="scheduler") as mocked_scheduler, \
             patch("agent_trader.runtime_entry.RuntimeSupervisor", return_value="supervisor") as mocked_supervisor, \
             patch("agent_trader.runtime_entry.RuntimeDaemon", return_value="daemon") as mocked_daemon:
            daemon = build_runtime_daemon(current_settings=self.settings, load_open_orders=lambda: [])

        self.assertEqual(daemon, "daemon")
        mocked_client.assert_called_once_with(self.settings)
        mocked_transport.assert_called_once()
        mocked_manager.assert_called_once()
        mocked_scheduler.assert_called_once()
        mocked_supervisor.assert_called_once()
        mocked_daemon.assert_called_once()


if __name__ == "__main__":
    unittest.main()
