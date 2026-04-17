import unittest

from agent_trader.models import AccountState, RiskLimits, TradeProposal
from agent_trader.risk import evaluate_trade


def _proposal(notional: float = 500.0, leverage: float = 2.0) -> TradeProposal:
    return TradeProposal(
        connector="okx_native",
        symbol="BTC-USDT-SWAP",
        side="buy",
        notional_usd=notional,
        leverage=leverage,
        expected_slippage_bps=5.0,
    )


def _limits(**overrides) -> RiskLimits:
    base = dict(
        max_notional_usd=10_000.0,
        max_leverage=10.0,
        daily_loss_limit_pct=10.0,
        max_slippage_bps=100.0,
        min_equity_usd=10.0,
    )
    base.update(overrides)
    return RiskLimits(**base)


class MarginAwareRiskTests(unittest.TestCase):
    def test_margin_checks_skipped_when_account_has_no_margin_info(self):
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
        )
        limits = _limits(min_margin_ratio=2.0, max_margin_utilization=0.3, min_available_equity_usd=200.0)
        decision = evaluate_trade(_proposal(), account, limits)
        self.assertTrue(decision.approved, decision.reasons)

    def test_margin_ratio_below_threshold_blocks_trade(self):
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=1,
            margin_ratio=1.2,
            available_equity_usd=4000.0,
            used_margin_usd=500.0,
        )
        limits = _limits(min_margin_ratio=2.0)
        decision = evaluate_trade(_proposal(), account, limits)
        self.assertFalse(decision.approved)
        self.assertIn("margin ratio below safety threshold", decision.reasons)

    def test_available_equity_floor_blocks_when_too_low(self):
        account = AccountState(
            equity_usd=5000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
            available_equity_usd=50.0,
        )
        limits = _limits(min_available_equity_usd=200.0)
        decision = evaluate_trade(_proposal(), account, limits)
        self.assertFalse(decision.approved)
        self.assertIn("available equity below minimum", decision.reasons)

    def test_margin_utilization_cap_blocks_additional_positions(self):
        # equity 1000, already using 400 margin, new trade wants 500/5 = 100 more
        # (400 + 100) / 1000 = 0.5 > 0.4 → reject
        account = AccountState(
            equity_usd=1000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=2000.0,
            open_positions=1,
            available_equity_usd=600.0,
            used_margin_usd=400.0,
        )
        limits = _limits(max_margin_utilization=0.4)
        decision = evaluate_trade(_proposal(notional=500.0, leverage=5.0), account, limits)
        self.assertFalse(decision.approved)
        self.assertIn("margin utilization exceeds cap", decision.reasons)

    def test_insufficient_available_margin_for_new_position_blocks(self):
        account = AccountState(
            equity_usd=1000.0,
            daily_pnl_pct=0.0,
            current_exposure_usd=0.0,
            open_positions=0,
            available_equity_usd=30.0,
            used_margin_usd=0.0,
        )
        # notional 500 at 5x → requires 100 initial margin; only 30 available
        decision = evaluate_trade(_proposal(notional=500.0, leverage=5.0), account, _limits())
        self.assertFalse(decision.approved)
        self.assertIn("insufficient available margin for new position", decision.reasons)

    def test_healthy_margin_state_still_approves(self):
        account = AccountState(
            equity_usd=10_000.0,
            daily_pnl_pct=0.2,
            current_exposure_usd=500.0,
            open_positions=1,
            available_equity_usd=8_000.0,
            margin_ratio=5.0,
            used_margin_usd=200.0,
        )
        limits = _limits(
            min_margin_ratio=2.0,
            max_margin_utilization=0.5,
            min_available_equity_usd=500.0,
        )
        decision = evaluate_trade(_proposal(notional=500.0, leverage=5.0), account, limits)
        self.assertTrue(decision.approved, decision.reasons)


if __name__ == "__main__":
    unittest.main()
