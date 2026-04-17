import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import healthcheck_payload, make_okx_client, okx_account_state_payload, process_signal_request_payload, run_okx_native_signal_pipeline
from agent_trader.models import AccountState, RiskLimits, StrategySignal
from agent_trader.okx_client import OKXCredentials


class MainOKXNativeTests(unittest.TestCase):
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
            signal_shared_secret="",
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

    def test_make_okx_client_builds_credentials_from_settings(self):
        with patch("agent_trader.main.OKXClient.from_credentials", return_value="okx-client") as mocked_factory:
            client = make_okx_client(self.settings)

        self.assertEqual(client, "okx-client")
        credentials = mocked_factory.call_args.args[0]
        self.assertEqual(credentials, OKXCredentials(api_key="k", api_secret="s", passphrase="p", flag="1"))
        self.assertEqual(mocked_factory.call_args.kwargs["td_mode"], "cross")

    def test_okx_account_state_payload_uses_native_sync(self):
        fake_state = AccountState(
            equity_usd=2000.0,
            daily_pnl_pct=1.5,
            current_exposure_usd=250.0,
            open_positions=1,
        )
        with patch("agent_trader.main.sync_okx_account_state", return_value=fake_state) as mocked_sync:
            payload = okx_account_state_payload(client=object(), current_settings=self.settings)

        self.assertEqual(
            payload,
            {
                "equity_usd": 2000.0,
                "daily_pnl_pct": 1.5,
                "current_exposure_usd": 250.0,
                "open_positions": 1,
                "available_equity_usd": None,
                "margin_ratio": None,
                "used_margin_usd": None,
                "positions_by_symbol": None,
                "positions_detail": None,
                "account_name": "primary",
                "connector": "okx_native",
                "symbol": "BTC-USDT-SWAP",
                "execution_path": "okx_native",
            },
        )
        mocked_sync.assert_called_once()

    def test_run_okx_native_signal_pipeline_executes_paper_path(self):
        signal = StrategySignal(
            side="buy",
            confidence=0.8,
            entry_price=50000.0,
            stop_loss_price=49000.0,
            take_profit_price=52000.0,
            expected_slippage_bps=5.0,
            leverage=2.0,
            rationale="trend continuation",
        )
        fake_account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )

        class FakeClient:
            def get_contract_value(self, symbol):
                return 0.01

        with patch("agent_trader.main.sync_okx_account_state", return_value=fake_account):
            payload = run_okx_native_signal_pipeline(signal=signal, client=FakeClient(), current_settings=self.settings)

        self.assertTrue(payload["risk"]["approved"])
        self.assertEqual(payload["execution"]["status"], "paper")
        self.assertEqual(payload["proposal"]["connector"], "okx_native")

    def test_process_signal_request_payload_builds_signal_and_runs_primary_pipeline(self):
        request_payload = {
            "side": "sell",
            "confidence": 0.7,
            "entry_price": 30000.0,
            "stop_loss_price": 30500.0,
            "take_profit_price": 28500.0,
            "expected_slippage_bps": 4.0,
            "leverage": 2.0,
            "rationale": "reversal",
            "client_signal_id": "sig-main-001",
        }
        with patch("agent_trader.main.run_primary_signal_pipeline", return_value={"status": "ok"}) as mocked_run:
            response = process_signal_request_payload(request_payload, client=object(), current_settings=self.settings, auth_header="")

        self.assertEqual(response, {"status": "ok"})
        signal = mocked_run.call_args.kwargs["signal"]
        self.assertEqual(signal.side, "sell")
        self.assertEqual(signal.entry_price, 30000.0)

    def test_healthcheck_payload_marks_okx_native_as_primary_path(self):
        payload = healthcheck_payload(self.settings)
        self.assertEqual(payload["execution_path"], "okx_native")
        self.assertEqual(payload["connector"], "okx_native")

    def tearDown(self):
        self.tempdir.cleanup()


if __name__ == "__main__":
    unittest.main()
