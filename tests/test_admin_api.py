import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader import admin_api
from agent_trader.config import Settings
from agent_trader.models import RiskLimits


def _build_settings(tmpdir: str, admin_secret: str = "adm1nSecret") -> Settings:
    return Settings(
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
        paper_mode=True,
        proposal_risk_fraction=0.1,
        audit_log_path=os.path.join(tmpdir, "audit", "events.jsonl"),
        signal_shared_secret="",
        signal_idempotency_path=os.path.join(tmpdir, "state", "signal_ids.txt"),
        control_state_path=os.path.join(tmpdir, "state", "control.json"),
        admin_shared_secret=admin_secret,
        admin_nonce_path=os.path.join(tmpdir, "state", "admin_nonces.txt"),
        admin_small_trade_usd=500.0,
        admin_large_trade_usd=5000.0,
        risk_limits=RiskLimits(
            max_notional_usd=10000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        ),
    )


def _signed(settings: Settings, path: str, body, timestamp: str, nonce: str):
    return admin_api.compute_hmac(settings.admin_shared_secret, timestamp, nonce, path, body)


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = _build_settings(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_handle_status_rejects_invalid_signature(self):
        ts = "1700000000"
        with self.assertRaises(admin_api.AdminAuthError):
            admin_api.handle_status(self.settings, ts, "n1", "deadbeef", now=int(ts))

    def test_handle_status_rejects_expired_timestamp(self):
        ts = "1000000000"
        sig = _signed(self.settings, "/admin/status", None, ts, "n2")
        with self.assertRaises(admin_api.AdminAuthError):
            admin_api.handle_status(self.settings, ts, "n2", sig, now=1700000000)

    def test_handle_status_returns_control_state(self):
        ts = "1700000100"
        sig = _signed(self.settings, "/admin/status", None, ts, "n3")
        payload = admin_api.handle_status(self.settings, ts, "n3", sig, now=int(ts))
        self.assertFalse(payload["trading_halted"])
        self.assertEqual(payload["execution_enabled"], True)

    def test_handle_halt_then_resume_persists_state(self):
        ts_halt = "1700000200"
        body_halt = {"reason": "manual pause", "actor": "hermes"}
        sig_halt = _signed(self.settings, "/admin/halt", body_halt, ts_halt, "n-halt")
        halt_resp = admin_api.handle_halt(self.settings, body_halt, ts_halt, "n-halt", sig_halt, now=int(ts_halt))
        self.assertTrue(halt_resp["trading_halted"])

        ts_resume = "1700000300"
        body_resume = {"actor": "hermes"}
        sig_resume = _signed(self.settings, "/admin/resume", body_resume, ts_resume, "n-resume")
        resume_resp = admin_api.handle_resume(self.settings, body_resume, ts_resume, "n-resume", sig_resume, now=int(ts_resume))
        self.assertFalse(resume_resp["trading_halted"])

        with open(self.settings.audit_log_path, "r", encoding="utf-8") as handle:
            actions = [json.loads(line)["action"] for line in handle]
        self.assertEqual(actions, ["halt", "resume"])

    def test_nonce_replay_is_rejected(self):
        ts = "1700000400"
        body = {"reason": "pause", "actor": "hermes"}
        sig = _signed(self.settings, "/admin/halt", body, ts, "dup-nonce")
        admin_api.handle_halt(self.settings, body, ts, "dup-nonce", sig, now=int(ts))
        with self.assertRaises(admin_api.AdminReplayError):
            admin_api.handle_halt(self.settings, body, ts, "dup-nonce", sig, now=int(ts))

    def test_manual_trade_small_tier_executes_without_confirmation(self):
        ts = "1700000500"
        body = {
            "side": "buy",
            "notional_usd": 100.0,
            "reference_price": 50000.0,
            "stop_loss_price": 49500.0,
            "take_profit_price": 51000.0,
            "expected_slippage_bps": 5.0,
            "leverage": 2.0,
            "actor": "hermes",
        }
        sig = _signed(self.settings, "/admin/manual_trade", body, ts, "n-small")

        captured = {}
        def fake_runner(signal, current_settings):
            captured["signal"] = signal
            return {"risk": {"approved": True}, "execution": {"status": "paper", "order_id": None}}

        result = admin_api.handle_manual_trade(
            self.settings, body, ts, "n-small", sig, pipeline_runner=fake_runner, now=int(ts)
        )
        self.assertEqual(result["tier"], "small")
        self.assertEqual(result["execution"]["status"], "paper")
        self.assertEqual(captured["signal"].side, "buy")

    def test_manual_trade_medium_tier_requires_confirmation(self):
        ts = "1700000600"
        body = {
            "side": "buy",
            "notional_usd": 1000.0,
            "reference_price": 50000.0,
            "stop_loss_price": 49500.0,
            "take_profit_price": 51000.0,
            "expected_slippage_bps": 5.0,
            "leverage": 2.0,
        }
        sig = _signed(self.settings, "/admin/manual_trade", body, ts, "n-med")
        with self.assertRaises(admin_api.AdminTierViolation):
            admin_api.handle_manual_trade(
                self.settings, body, ts, "n-med", sig, pipeline_runner=lambda **_: {}, now=int(ts)
            )

    def test_manual_trade_large_tier_requires_pin(self):
        ts = "1700000700"
        body = {
            "side": "buy",
            "notional_usd": 6000.0,
            "reference_price": 50000.0,
            "stop_loss_price": 49500.0,
            "take_profit_price": 51000.0,
            "expected_slippage_bps": 5.0,
            "leverage": 2.0,
            "confirmation": "confirmed",
        }
        sig = _signed(self.settings, "/admin/manual_trade", body, ts, "n-large-nopin")
        with self.assertRaises(admin_api.AdminTierViolation):
            admin_api.handle_manual_trade(
                self.settings, body, ts, "n-large-nopin", sig, pipeline_runner=lambda **_: {}, now=int(ts)
            )

        body_with_pin = dict(body, pin=self.settings.admin_shared_secret)
        sig2 = _signed(self.settings, "/admin/manual_trade", body_with_pin, ts, "n-large-pin")
        result = admin_api.handle_manual_trade(
            self.settings,
            body_with_pin,
            ts,
            "n-large-pin",
            sig2,
            pipeline_runner=lambda signal, current_settings: {"risk": {"approved": True}, "execution": {"status": "paper"}},
            now=int(ts),
        )
        self.assertEqual(result["tier"], "large")


class AdminApiControlStateIntegrationTests(unittest.TestCase):
    def test_main_pipeline_respects_persistent_halt(self):
        from agent_trader.main import _apply_control_state
        from agent_trader.control_state import halt_trading

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _build_settings(tmpdir)
            halt_trading(settings.control_state_path, reason="test", actor="t")
            limits = _apply_control_state(settings)
        self.assertTrue(limits.trading_halted)


if __name__ == "__main__":
    unittest.main()
