import unittest

from agent_trader.models import AccountState, RiskLimits, TradeProposal
from agent_trader.risk import evaluate_trade


def _proposal(symbol: str = "BTC-USDT-SWAP", notional: float = 500.0) -> TradeProposal:
    return TradeProposal(
        connector="okx_native",
        symbol=symbol,
        side="buy",
        notional_usd=notional,
        leverage=2.0,
        expected_slippage_bps=5.0,
    )


def _limits(**overrides) -> RiskLimits:
    base = dict(
        max_notional_usd=20_000.0,
        max_leverage=10.0,
        daily_loss_limit_pct=10.0,
        max_slippage_bps=100.0,
        min_equity_usd=10.0,
    )
    base.update(overrides)
    return RiskLimits(**base)


def _account(**overrides) -> AccountState:
    base = dict(
        equity_usd=10_000.0,
        daily_pnl_pct=0.0,
        current_exposure_usd=0.0,
        open_positions=0,
    )
    base.update(overrides)
    return AccountState(**base)


class MultiSymbolRiskTests(unittest.TestCase):
    def test_symbol_missing_blocks_trade(self):
        proposal = TradeProposal(
            connector="okx_native",
            symbol="",
            side="buy",
            notional_usd=100.0,
            leverage=1.0,
            expected_slippage_bps=5.0,
        )
        decision = evaluate_trade(proposal, _account(), _limits())
        self.assertFalse(decision.approved)
        self.assertIn("symbol required", decision.reasons)

    def test_allowlist_rejects_unknown_symbol(self):
        allow = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
        decision = evaluate_trade(_proposal(symbol="DOGE-USDT-SWAP"), _account(), _limits(), allowed_symbols=allow)
        self.assertFalse(decision.approved)
        self.assertIn("symbol not in allowed list", decision.reasons)

    def test_allowlist_accepts_known_symbol(self):
        allow = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
        decision = evaluate_trade(_proposal(symbol="ETH-USDT-SWAP"), _account(), _limits(), allowed_symbols=allow)
        self.assertTrue(decision.approved, decision.reasons)

    def test_empty_allowlist_allows_any_symbol(self):
        decision = evaluate_trade(_proposal(symbol="DOGE-USDT-SWAP"), _account(), _limits(), allowed_symbols=())
        self.assertTrue(decision.approved, decision.reasons)

    def test_per_symbol_cap_blocks_when_exposure_would_exceed(self):
        account = _account(
            current_exposure_usd=1500.0,
            positions_by_symbol={"BTC-USDT-SWAP": 800.0, "ETH-USDT-SWAP": 700.0},
        )
        limits = _limits(max_notional_per_symbol_usd=1000.0)
        decision = evaluate_trade(_proposal(symbol="BTC-USDT-SWAP", notional=500.0), account, limits)
        self.assertFalse(decision.approved)
        self.assertIn("per-symbol notional limit exceeded", decision.reasons)

    def test_per_symbol_cap_ignores_other_symbols(self):
        account = _account(
            current_exposure_usd=1500.0,
            positions_by_symbol={"BTC-USDT-SWAP": 900.0, "ETH-USDT-SWAP": 600.0},
        )
        limits = _limits(max_notional_per_symbol_usd=1000.0)
        decision = evaluate_trade(_proposal(symbol="SOL-USDT-SWAP", notional=500.0), account, limits)
        self.assertTrue(decision.approved, decision.reasons)

    def test_per_symbol_cap_disabled_when_limit_zero(self):
        account = _account(positions_by_symbol={"BTC-USDT-SWAP": 5000.0})
        decision = evaluate_trade(_proposal(symbol="BTC-USDT-SWAP", notional=500.0), account, _limits())
        self.assertTrue(decision.approved, decision.reasons)

    def test_per_symbol_cap_skipped_when_positions_unknown(self):
        # account.positions_by_symbol is None → skip check even if limit is set
        decision = evaluate_trade(
            _proposal(symbol="BTC-USDT-SWAP", notional=500.0),
            _account(),
            _limits(max_notional_per_symbol_usd=100.0),
        )
        self.assertTrue(decision.approved, decision.reasons)


if __name__ == "__main__":
    unittest.main()
