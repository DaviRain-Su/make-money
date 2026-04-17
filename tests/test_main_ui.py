import json
import os
import tempfile
import unittest

from agent_trader.config import Settings
from agent_trader.main import build_ui_summary_payload, ui_halt_action, ui_resume_action
from agent_trader.models import AccountState, RiskLimits


def _settings(tmpdir: str) -> Settings:
    return Settings(
        environment="dev",
        okx_connector_id="okx_native",
        okx_symbol="BTC-USDT-SWAP",
        okx_api_key="",
        okx_api_secret="",
        okx_passphrase="",
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
        paper_mode=True,
        proposal_risk_fraction=0.1,
        audit_log_path=os.path.join(tmpdir, "audit", "events.jsonl"),
        signal_shared_secret="",
        signal_idempotency_path=os.path.join(tmpdir, "state", "signal_ids.txt"),
        control_state_path=os.path.join(tmpdir, "state", "control.json"),
        admin_shared_secret="s",
        admin_nonce_path=os.path.join(tmpdir, "state", "admin_nonces.txt"),
        admin_small_trade_usd=500.0,
        admin_large_trade_usd=5000.0,
        risk_limits=RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        ),
    )


class MainUITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = _settings(self.tempdir.name)
        os.makedirs(os.path.dirname(self.settings.audit_log_path), exist_ok=True)
        with open(self.settings.audit_log_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_type": "risk_decision", "risk_approved": False, "timestamp": "2026-04-17T00:00:00+00:00"}) + "\n")
            handle.write(json.dumps({"event_type": "order_submitted", "execution_status": "submitted", "timestamp": "2026-04-17T00:00:01+00:00"}) + "\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_build_ui_summary_payload_aggregates_status_events_counters(self):
        def account_fn(_resolved):
            return {
                "equity_usd": 1200.0,
                "daily_pnl_pct": 0.5,
                "current_exposure_usd": 300.0,
                "open_positions": 1,
                "connector": "okx_native",
                "symbol": "BTC-USDT-SWAP",
            }
        payload = build_ui_summary_payload(current_settings=self.settings, account_fn=account_fn)
        self.assertFalse(payload["trading_halted"])
        self.assertEqual(payload["counters"], {"risk_blocked": 1, "orders_submitted": 1, "orders_filled": 0, "admin_actions": 0})
        self.assertEqual(payload["account"]["equity_usd"], 1200.0)
        self.assertEqual(len(payload["events"]), 2)
        self.assertEqual(payload["symbol"], "BTC-USDT-SWAP")

    def test_build_ui_summary_payload_reports_account_error_without_failing(self):
        def bad_fn(_resolved):
            raise RuntimeError("upstream offline")
        payload = build_ui_summary_payload(current_settings=self.settings, account_fn=bad_fn)
        self.assertIsNone(payload["account"])
        self.assertIn("upstream offline", payload["account_error"])

    def test_ui_halt_and_resume_write_admin_action_events(self):
        ui_halt_action(reason="dashboard pause", actor="local-ui", current_settings=self.settings)
        ui_resume_action(actor="local-ui", current_settings=self.settings)
        with open(self.settings.audit_log_path, "r", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        admin_rows = [row for row in rows if row.get("event_type") == "admin_action"]
        self.assertEqual([row["action"] for row in admin_rows], ["halt", "resume"])
        self.assertTrue(all(row.get("source") == "local_ui" for row in admin_rows))

    def test_ui_halt_flows_into_build_summary(self):
        ui_halt_action(reason="oops", actor="local-ui", current_settings=self.settings)
        payload = build_ui_summary_payload(current_settings=self.settings, account_fn=None)
        self.assertTrue(payload["trading_halted"])
        self.assertEqual(payload["halt_reason"], "oops")
        self.assertEqual(payload["halted_by"], "local-ui")
        self.assertIsNone(payload["account"])


if __name__ == "__main__":
    unittest.main()
