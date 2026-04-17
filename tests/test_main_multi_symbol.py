import os
import tempfile
import unittest
from unittest.mock import patch

from agent_trader.config import Settings
from agent_trader.main import process_signal_request_payload, run_okx_native_signal_pipeline
from agent_trader.models import AccountState, RiskLimits, StrategySignal


def _settings(tmpdir: str, allowed=()) -> Settings:
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
        admin_shared_secret="admsecret",
        admin_nonce_path=os.path.join(tmpdir, "state", "admin_nonces.txt"),
        admin_small_trade_usd=500.0,
        admin_large_trade_usd=5000.0,
        risk_limits=RiskLimits(
            max_notional_usd=5000.0,
            max_leverage=5.0,
            daily_loss_limit_pct=10.0,
            max_slippage_bps=50.0,
        ),
        okx_allowed_symbols=allowed,
    )


class MainMultiSymbolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_signal_payload_symbol_overrides_default(self):
        settings = _settings(self.tempdir.name)
        fake_account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )

        class FakeClient:
            def get_contract_value(self, _symbol):
                return 0.1

        with patch("agent_trader.main.sync_okx_account_state", return_value=fake_account):
            signal = StrategySignal(
                side="buy",
                confidence=0.8,
                entry_price=3000.0,
                stop_loss_price=2950.0,
                take_profit_price=3100.0,
                expected_slippage_bps=5.0,
                leverage=2.0,
                rationale="",
                symbol="ETH-USDT-SWAP",
            )
            result = run_okx_native_signal_pipeline(signal=signal, client=FakeClient(), current_settings=settings)
        self.assertEqual(result["proposal"]["symbol"], "ETH-USDT-SWAP")
        self.assertTrue(result["risk"]["approved"], result["risk"]["reasons"])

    def test_signal_rejected_when_symbol_not_in_allowlist(self):
        settings = _settings(self.tempdir.name, allowed=("BTC-USDT-SWAP", "ETH-USDT-SWAP"))
        fake_account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )

        class FakeClient:
            def get_contract_value(self, _symbol):
                return 0.1

        with patch("agent_trader.main.sync_okx_account_state", return_value=fake_account):
            signal = StrategySignal(
                side="buy",
                confidence=0.5,
                entry_price=1.0,
                stop_loss_price=0.95,
                take_profit_price=1.05,
                expected_slippage_bps=5.0,
                leverage=1.0,
                rationale="",
                symbol="DOGE-USDT-SWAP",
            )
            result = run_okx_native_signal_pipeline(signal=signal, client=FakeClient(), current_settings=settings)
        self.assertFalse(result["risk"]["approved"])
        self.assertIn("symbol not in allowed list", result["risk"]["reasons"])
        self.assertEqual(result["execution"]["status"], "blocked")

    def test_process_signal_request_payload_passes_symbol_into_signal(self):
        settings = _settings(self.tempdir.name)
        captured = {}
        def fake_pipeline(signal, client=None, current_settings=None):
            captured["signal"] = signal
            return {"risk": {"approved": True}, "execution": {"status": "paper"}}
        with patch("agent_trader.main.run_primary_signal_pipeline", side_effect=fake_pipeline):
            process_signal_request_payload(
                {
                    "side": "buy",
                    "confidence": 0.8,
                    "entry_price": 3000.0,
                    "stop_loss_price": 2950.0,
                    "take_profit_price": 3100.0,
                    "expected_slippage_bps": 5.0,
                    "leverage": 2.0,
                    "symbol": "ETH-USDT-SWAP",
                    "client_signal_id": "sig-multi-1",
                },
                current_settings=settings,
            )
        self.assertEqual(captured["signal"].symbol, "ETH-USDT-SWAP")


if __name__ == "__main__":
    unittest.main()
