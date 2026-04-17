import unittest

from agent_trader.main import process_signal_payload
from agent_trader.models import AccountState, RiskLimits, StrategySignal


class FakeClient:
    pass


class PipelineTests(unittest.TestCase):
    def test_process_signal_payload_denies_when_risk_engine_rejects(self):
        signal = StrategySignal(
            side="buy",
            confidence=1.0,
            entry_price=50000.0,
            stop_loss_price=49000.0,
            take_profit_price=52000.0,
            expected_slippage_bps=50.0,
            leverage=4.0,
            rationale="too aggressive",
        )
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=-3.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )
        limits = RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        )

        payload = process_signal_payload(
            signal=signal,
            account=account,
            client=FakeClient(),
            connector="okx_perpetual",
            symbol="BTC-USDT-SWAP",
            account_name="primary",
            risk_limits=limits,
            risk_fraction=0.1,
            execution_enabled=False,
            paper_mode=True,
        )

        self.assertFalse(payload["risk"]["approved"])
        self.assertEqual(payload["execution"]["status"], "blocked")
        self.assertIn("daily loss limit breached", payload["risk"]["reasons"])


if __name__ == "__main__":
    unittest.main()
