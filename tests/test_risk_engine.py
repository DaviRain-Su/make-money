import unittest

from agent_trader.models import AccountState, RiskLimits, TradeProposal
from agent_trader.risk import evaluate_trade


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.limits = RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        )
        self.account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=-0.5,
            current_exposure_usd=0.0,
            open_positions=0,
        )

    def test_approves_trade_within_limits(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="buy",
            notional_usd=500.0,
            leverage=2.0,
            expected_slippage_bps=5.0,
        )

        decision = evaluate_trade(proposal, self.account, self.limits)

        self.assertTrue(decision.approved)
        self.assertEqual(decision.reasons, [])

    def test_denies_trade_when_cumulative_notional_exceeds_limit(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="buy",
            notional_usd=300.0,
            leverage=2.0,
            expected_slippage_bps=5.0,
        )
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=800.0,
            open_positions=1,
        )

        decision = evaluate_trade(proposal, account, self.limits)

        self.assertFalse(decision.approved)
        self.assertIn("notional limit exceeded", decision.reasons)

    def test_denies_trade_when_daily_loss_limit_breached(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="sell",
            notional_usd=200.0,
            leverage=1.0,
            expected_slippage_bps=3.0,
        )
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=-2.5,
            current_exposure_usd=0.0,
            open_positions=0,
        )

        decision = evaluate_trade(proposal, account, self.limits)

        self.assertFalse(decision.approved)
        self.assertIn("daily loss limit breached", decision.reasons)

    def test_denies_non_positive_values_and_low_equity(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="BUY",
            notional_usd=0.0,
            leverage=0.5,
            expected_slippage_bps=-1.0,
        )
        account = AccountState(
            equity_usd=25.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )

        decision = evaluate_trade(proposal, account, self.limits)

        self.assertFalse(decision.approved)
        self.assertIn("notional must be positive", decision.reasons)
        self.assertIn("leverage must be at least 1", decision.reasons)
        self.assertIn("slippage must be positive", decision.reasons)
        self.assertIn("equity below minimum", decision.reasons)

    def test_denies_trade_when_halt_flag_is_set(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="buy",
            notional_usd=100.0,
            leverage=1.0,
            expected_slippage_bps=2.0,
        )
        limits = RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
            trading_halted=True,
        )

        decision = evaluate_trade(proposal, self.account, limits)

        self.assertFalse(decision.approved)
        self.assertIn("trading halted", decision.reasons)


if __name__ == "__main__":
    unittest.main()
