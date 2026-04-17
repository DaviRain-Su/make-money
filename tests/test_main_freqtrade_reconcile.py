import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import _maybe_reconcile_freqtrade
from agent_trader.models import RiskLimits


def _settings(tmpdir, enable_reconcile=True, url="http://freqtrade.local:8080") -> Settings:
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
        freqtrade_api_url=url,
        freqtrade_api_username="u",
        freqtrade_api_password="p",
        freqtrade_reconcile_on_block=enable_reconcile,
    )


class MaybeReconcileFreqtradeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_returns_none_when_reconcile_disabled(self):
        settings = _settings(self.tempdir.name, enable_reconcile=False)
        result = _maybe_reconcile_freqtrade(
            payload={"trade_id": 1},
            pipeline_result={"execution": {"status": "blocked"}, "risk": {"reasons": ["x"]}},
            current_settings=settings,
        )
        self.assertIsNone(result)

    def test_returns_none_when_execution_not_blocked(self):
        settings = _settings(self.tempdir.name)
        result = _maybe_reconcile_freqtrade(
            payload={"trade_id": 1},
            pipeline_result={"execution": {"status": "paper"}, "risk": {"approved": True}},
            current_settings=settings,
        )
        self.assertIsNone(result)

    def test_skips_when_no_trade_id(self):
        settings = _settings(self.tempdir.name)
        result = _maybe_reconcile_freqtrade(
            payload={},
            pipeline_result={"execution": {"status": "blocked"}, "risk": {"reasons": ["halt"]}},
            current_settings=settings,
        )
        self.assertEqual(result, {"status": "skipped", "reason": "no trade_id"})

    def test_skips_when_api_url_missing(self):
        settings = _settings(self.tempdir.name, url="")
        result = _maybe_reconcile_freqtrade(
            payload={"trade_id": 5},
            pipeline_result={"execution": {"status": "blocked"}, "risk": {"reasons": ["halt"]}},
            current_settings=settings,
        )
        self.assertEqual(result["status"], "skipped")

    def test_calls_force_exit_and_logs_audit_event(self):
        settings = _settings(self.tempdir.name)
        with patch("agent_trader.main.force_exit_trade", return_value={"ok": True}) as mocked:
            result = _maybe_reconcile_freqtrade(
                payload={"trade_id": 99},
                pipeline_result={"execution": {"status": "blocked"}, "risk": {"reasons": ["notional limit exceeded"]}},
                current_settings=settings,
            )
        mocked.assert_called_once()
        self.assertEqual(result, {"status": "ok", "trade_id": 99})
        # Audit event should be present
        with open(settings.audit_log_path, "r", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        self.assertTrue(any(r.get("event_type") == "freqtrade_reconcile" and r.get("trade_id") == 99 for r in rows))

    def test_records_error_outcome_when_transport_fails(self):
        settings = _settings(self.tempdir.name)
        def boom(*_a, **_kw):
            raise RuntimeError("freqtrade offline")
        with patch("agent_trader.main.force_exit_trade", side_effect=boom):
            result = _maybe_reconcile_freqtrade(
                payload={"trade_id": 7},
                pipeline_result={"execution": {"status": "blocked"}, "risk": {"reasons": ["x"]}},
                current_settings=settings,
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("freqtrade offline", result["error"])


if __name__ == "__main__":
    unittest.main()
