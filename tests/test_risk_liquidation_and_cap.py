import unittest

from agent_trader.models import AccountState, RiskLimits, TradeProposal
from agent_trader.risk import evaluate_trade


def _proposal(symbol: str = "BTC-USDT-SWAP", action: str = "OPEN") -> TradeProposal:
    return TradeProposal(
        connector="okx_native",
        symbol=symbol,
        side="buy",
        notional_usd=100.0,
        leverage=2.0,
        expected_slippage_bps=5.0,
        position_action=action,
    )


def _limits(**overrides) -> RiskLimits:
    base = dict(
        max_notional_usd=100_000.0,
        max_leverage=10.0,
        daily_loss_limit_pct=50.0,
        max_slippage_bps=100.0,
        min_equity_usd=10.0,
    )
    base.update(overrides)
    return RiskLimits(**base)


def _account(**overrides) -> AccountState:
    base = dict(
        equity_usd=5000.0,
        daily_pnl_pct=0.0,
        current_exposure_usd=0.0,
        open_positions=0,
    )
    base.update(overrides)
    return AccountState(**base)


class LiquidationGuardTests(unittest.TestCase):
    def test_rejects_open_when_any_position_near_liquidation(self):
        account = _account(
            positions_by_symbol={"ETH-USDT-SWAP": 500.0},
            positions_detail={"ETH-USDT-SWAP": {"distance_pct": 0.03, "side": "long"}},
        )
        decision = evaluate_trade(
            _proposal(symbol="BTC-USDT-SWAP"),
            account,
            _limits(min_liquidation_distance_pct=0.05),
        )
        self.assertFalse(decision.approved)
        self.assertIn("position near liquidation", decision.reasons)

    def test_allows_close_even_when_positions_near_liquidation(self):
        account = _account(
            positions_by_symbol={"ETH-USDT-SWAP": 500.0},
            positions_detail={"ETH-USDT-SWAP": {"distance_pct": 0.02}},
        )
        decision = evaluate_trade(
            _proposal(symbol="ETH-USDT-SWAP", action="CLOSE"),
            account,
            _limits(min_liquidation_distance_pct=0.1),
        )
        self.assertTrue(decision.approved, decision.reasons)

    def test_missing_distance_is_ignored(self):
        account = _account(
            positions_by_symbol={"ETH-USDT-SWAP": 500.0},
            positions_detail={"ETH-USDT-SWAP": {"distance_pct": None}},
        )
        decision = evaluate_trade(
            _proposal(symbol="BTC-USDT-SWAP"),
            account,
            _limits(min_liquidation_distance_pct=0.1),
        )
        self.assertTrue(decision.approved, decision.reasons)


class MaxOpenPositionsTests(unittest.TestCase):
    def test_rejects_new_symbol_when_cap_hit(self):
        account = _account(
            positions_by_symbol={"A": 100.0, "B": 100.0, "C": 100.0},
        )
        decision = evaluate_trade(
            _proposal(symbol="D"),
            account,
            _limits(max_open_positions=3),
        )
        self.assertFalse(decision.approved)
        self.assertIn("too many open positions", decision.reasons)

    def test_allows_adding_to_existing_position_at_cap(self):
        account = _account(
            positions_by_symbol={"A": 100.0, "B": 100.0, "C": 100.0},
        )
        decision = evaluate_trade(
            _proposal(symbol="A"),
            account,
            _limits(max_open_positions=3),
        )
        self.assertTrue(decision.approved, decision.reasons)

    def test_allows_close_regardless_of_cap(self):
        account = _account(
            positions_by_symbol={"A": 100.0, "B": 100.0, "C": 100.0},
        )
        decision = evaluate_trade(
            _proposal(symbol="D", action="CLOSE"),
            account,
            _limits(max_open_positions=3),
        )
        self.assertTrue(decision.approved, decision.reasons)

    def test_cap_disabled_by_default(self):
        account = _account(positions_by_symbol={f"S{i}": 50.0 for i in range(20)})
        decision = evaluate_trade(_proposal(symbol="BRAND-NEW"), account, _limits())
        self.assertTrue(decision.approved, decision.reasons)


if __name__ == "__main__":
    unittest.main()
