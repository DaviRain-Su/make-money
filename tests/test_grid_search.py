import unittest

from agent_trader.grid_search import GridSearchRow, grid_search_ema_atr
from agent_trader.models import RiskLimits
from agent_trader.strategy import Candle


def _flat_then_spike(flat_bars: int = 60, trigger_up: bool = True):
    candles = []
    for i in range(flat_bars):
        candles.append(Candle(ts=i * 1000, open=100, high=100.5, low=99.5, close=100))
    # spike to trigger crossover
    price = 110 if trigger_up else 90
    candles.append(Candle(ts=flat_bars * 1000, open=100, high=price + 1, low=99.5, close=price))
    # follow-through bar that hits the TP for a fast_ema=5, slow_ema=20 setup
    candles.append(Candle(ts=(flat_bars + 1) * 1000, open=price, high=price + 15, low=price - 5, close=price + 10))
    return candles


def _limits() -> RiskLimits:
    return RiskLimits(
        max_notional_usd=10_000.0,
        max_leverage=10.0,
        daily_loss_limit_pct=50.0,
        max_slippage_bps=100.0,
        min_equity_usd=10.0,
    )


class GridSearchTests(unittest.TestCase):
    def test_empty_param_grid_returns_no_rows(self):
        result = grid_search_ema_atr(
            candles_by_symbol={"BTC-USDT-SWAP": _flat_then_spike()},
            param_grid={},
            initial_equity_usd=1000.0,
            risk_limits=_limits(),
        )
        self.assertEqual(result.rows, [])

    def test_sweeps_cartesian_product(self):
        candles = _flat_then_spike()
        result = grid_search_ema_atr(
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            param_grid={"fast_ema": [3, 5], "slow_ema": [10, 20]},
            initial_equity_usd=1000.0,
            risk_limits=_limits(),
            min_bars_for_signal=20,
        )
        # 4 combos, all valid (fast < slow in each case)
        self.assertEqual(len(result.rows), 4)

    def test_invalid_combos_are_skipped(self):
        candles = _flat_then_spike()
        result = grid_search_ema_atr(
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            param_grid={"fast_ema": [10, 20], "slow_ema": [5, 30]},
            initial_equity_usd=1000.0,
            risk_limits=_limits(),
            min_bars_for_signal=20,
        )
        # (10,5) and (20,5) skipped; (10,30), (20,30) kept
        self.assertEqual(len(result.rows), 2)

    def test_ranked_by_score_sorts_by_pnl_minus_penalties(self):
        # Two synthetic rows with constructed reports
        from agent_trader.backtest import BacktestReport, ClosedTrade

        rowA = GridSearchRow(
            params={"fast_ema": 5, "slow_ema": 20},
            report=BacktestReport(
                initial_equity_usd=1000.0,
                final_equity_usd=1500.0,
                signals_total=10,
                signals_approved=10,
                signals_blocked=0,
                block_reasons={},
                closed_trades=[ClosedTrade(
                    symbol="BTC", side="buy", entry_price=100, exit_price=150,
                    stop_loss_price=95, take_profit_price=150, notional_usd=100,
                    entered_at=0, exited_at=1, exit_reason="take_profit", pnl_usd=500.0, pnl_pct=50.0,
                )],
                blocked_signals=[],
            ),
        )
        rowB = GridSearchRow(
            params={"fast_ema": 10, "slow_ema": 20},
            report=BacktestReport(
                initial_equity_usd=1000.0,
                final_equity_usd=1200.0,
                signals_total=10,
                signals_approved=2,
                signals_blocked=8,
                block_reasons={"notional limit exceeded": 8},
                closed_trades=[ClosedTrade(
                    symbol="BTC", side="buy", entry_price=100, exit_price=120,
                    stop_loss_price=95, take_profit_price=120, notional_usd=100,
                    entered_at=0, exited_at=1, exit_reason="take_profit", pnl_usd=200.0, pnl_pct=20.0,
                )],
                blocked_signals=[],
            ),
        )
        from agent_trader.grid_search import GridSearchResult
        ranked = GridSearchResult(rows=[rowB, rowA]).ranked_by_score()
        self.assertEqual(ranked[0].params, rowA.params)

    def test_summary_includes_top_block_reasons(self):
        from agent_trader.backtest import BacktestReport
        row = GridSearchRow(
            params={"fast_ema": 5, "slow_ema": 20},
            report=BacktestReport(
                initial_equity_usd=1000.0,
                final_equity_usd=1000.0,
                signals_total=5,
                signals_approved=1,
                signals_blocked=4,
                block_reasons={"A": 3, "B": 1, "C": 1},
                closed_trades=[],
                blocked_signals=[],
            ),
        )
        summary = row.summary()
        self.assertEqual(summary["block_rate"], 0.8)
        self.assertEqual(summary["top_block_reasons"], {"A": 3, "B": 1, "C": 1})


if __name__ == "__main__":
    unittest.main()
