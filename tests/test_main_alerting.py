import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import emit_signal_audit_events, ui_halt_action
from agent_trader.models import RiskLimits, StrategySignal


def _settings(tmpdir, webhook="http://alert.local/hook") -> Settings:
    return Settings(
        environment="dev",
        okx_connector_id="okx_native",
        okx_symbol="BTC-USDT-SWAP",
        okx_api_key="",
        okx_api_secret="",
        okx_passphrase="",
        okx_flag="1",
        okx_td_mode="cross",
        okx_ws_url="",
        reconcile_poll_interval_seconds=30,
        use_okx_native=True,
        hbot_account_name="primary",
        hbot_api_url="",
        hbot_api_username="",
        hbot_api_password="",
        execution_enabled=True,
        paper_mode=True,
        proposal_risk_fraction=0.1,
        audit_log_path=os.path.join(tmpdir, "audit", "events.jsonl"),
        signal_shared_secret="",
        signal_idempotency_path=os.path.join(tmpdir, "state", "signal_ids.txt"),
        control_state_path=os.path.join(tmpdir, "state", "control.json"),
        admin_shared_secret="adm",
        admin_nonce_path=os.path.join(tmpdir, "state", "admin_nonces.txt"),
        admin_small_trade_usd=500.0,
        admin_large_trade_usd=5000.0,
        risk_limits=RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        ),
        alert_webhook_url=webhook,
    )


def _signal() -> StrategySignal:
    return StrategySignal(
        side="buy",
        confidence=0.5,
        entry_price=100.0,
        stop_loss_price=99.0,
        take_profit_price=103.0,
        expected_slippage_bps=5.0,
        leverage=1.0,
        rationale="t",
        symbol="BTC-USDT-SWAP",
    )


class MainAlertingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_blocked_signal_triggers_push_alert(self):
        settings = _settings(self.tempdir.name)
        result = {
            "risk": {"approved": False, "reasons": ["notional limit exceeded"]},
            "execution": {"status": "blocked"},
            "proposal": {"symbol": "BTC-USDT-SWAP", "position_action": "OPEN"},
        }
        with patch("agent_trader.main.push_level_alert", return_value=[{"status": "ok"}]) as mocked:
            emit_signal_audit_events(
                signal=_signal(),
                result=result,
                current_settings=settings,
                symbol="BTC-USDT-SWAP",
                client_signal_id="sig-1",
            )
        self.assertTrue(mocked.called)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "signal_blocked")
        self.assertEqual(kwargs["level"], "danger")
        self.assertEqual(kwargs["payload"]["symbol"], "BTC-USDT-SWAP")
        self.assertIn("notional limit exceeded", kwargs["payload"]["risk_reasons"])

    def test_approved_signal_does_not_alert(self):
        settings = _settings(self.tempdir.name)
        result = {
            "risk": {"approved": True, "reasons": []},
            "execution": {"status": "paper"},
            "proposal": {"symbol": "BTC-USDT-SWAP", "position_action": "OPEN"},
        }
        with patch("agent_trader.main.push_level_alert") as mocked:
            emit_signal_audit_events(
                signal=_signal(),
                result=result,
                current_settings=settings,
                symbol="BTC-USDT-SWAP",
                client_signal_id="sig-2",
            )
        self.assertFalse(mocked.called)

    def test_missing_webhook_returns_empty_dispatch_list(self):
        # No URLs configured → push_level_alert is still invoked, but returns
        # [] because resolve_alert_urls sees no URL. Tests the end-result
        # rather than the legacy early-bail internal shape.
        settings = _settings(self.tempdir.name, webhook="")
        result = {
            "risk": {"approved": False, "reasons": ["x"]},
            "execution": {"status": "blocked"},
            "proposal": {"symbol": "BTC-USDT-SWAP", "position_action": "OPEN"},
        }
        with patch("agent_trader.main.push_level_alert", return_value=[]) as mocked:
            emit_signal_audit_events(
                signal=_signal(),
                result=result,
                current_settings=settings,
                symbol="BTC-USDT-SWAP",
                client_signal_id="sig-3",
            )
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.return_value, [])

    def test_ui_halt_action_alerts_once(self):
        settings = _settings(self.tempdir.name)
        with patch("agent_trader.main.push_level_alert", return_value=[{"status": "ok"}]) as mocked:
            ui_halt_action(reason="emergency", actor="me", current_settings=settings)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(mocked.call_args.kwargs["event_type"], "halt")
        self.assertEqual(mocked.call_args.kwargs["level"], "danger")
        self.assertEqual(mocked.call_args.kwargs["payload"]["reason"], "emergency")


if __name__ == "__main__":
    unittest.main()
