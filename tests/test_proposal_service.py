import unittest

from agent_trader.models import AccountState, RiskLimits, StrategySignal
from agent_trader.proposal_service import build_trade_proposal


class ProposalServiceTests(unittest.TestCase):
    def setUp(self):
        self.limits = RiskLimits(
            max_notional_usd=1000.0,
            max_leverage=3.0,
            daily_loss_limit_pct=2.0,
            max_slippage_bps=15.0,
        )
        self.account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.5,
            current_exposure_usd=100.0,
            open_positions=1,
        )

    def test_build_trade_proposal_uses_stop_distance_and_caps_remaining_exposure(self):
        signal = StrategySignal(
            side="BUY",
            confidence=0.8,
            entry_price=50000.0,
            stop_loss_price=49250.0,
            take_profit_price=52000.0,
            expected_slippage_bps=4.0,
            leverage=2.0,
            rationale="trend continuation",
        )

        proposal = build_trade_proposal(
            signal=signal,
            account=self.account,
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            risk_limits=self.limits,
            risk_fraction=0.1,
        )

        self.assertEqual(proposal.connector, "okx_native")
        self.assertEqual(proposal.symbol, "BTC-USDT-SWAP")
        self.assertEqual(proposal.side, "buy")
        self.assertEqual(proposal.leverage, 2.0)
        self.assertEqual(proposal.expected_slippage_bps, 4.0)
        self.assertEqual(proposal.notional_usd, 900.0)
        self.assertEqual(proposal.stop_loss_price, 49250.0)
        self.assertEqual(proposal.take_profit_price, 52000.0)
        self.assertEqual(proposal.position_action, "OPEN")

    def test_build_trade_proposal_clamps_leverage_and_supports_close_action(self):
        signal = StrategySignal(
            side="sell",
            confidence=1.0,
            entry_price=2500.0,
            stop_loss_price=2550.0,
            take_profit_price=2300.0,
            expected_slippage_bps=6.0,
            leverage=10.0,
            rationale="mean reversion",
            position_action="close",
            pos_side="short",
        )

        proposal = build_trade_proposal(
            signal=signal,
            account=self.account,
            connector="okx_native",
            symbol="ETH-USDT-SWAP",
            risk_limits=self.limits,
            risk_fraction=0.02,
        )

        self.assertEqual(proposal.leverage, 3.0)
        self.assertEqual(proposal.position_action, "CLOSE")
        self.assertEqual(proposal.pos_side, "short")


if __name__ == "__main__":
    unittest.main()
