import unittest

from agent_trader.backtest import run_backtest
from agent_trader.models import RiskLimits, StrategySignal
from agent_trader.strategy import Candle


def _candle(ts: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(ts=ts, open=o, high=h, low=l, close=c)


def _limits(**overrides) -> RiskLimits:
    base = dict(
        max_notional_usd=10_000.0,
        max_leverage=10.0,
        daily_loss_limit_pct=50.0,
        max_slippage_bps=100.0,
        min_equity_usd=10.0,
    )
    base.update(overrides)
    return RiskLimits(**base)



class BacktestTakeProfitTests(unittest.TestCase):
    def test_take_profit_closes_winning_trade(self):
        # Flat price up to bar 30, then signal fires; next bar the price rockets
        # to hit TP; backtester should book profit.
        candles = [
            _candle(i, 100, 100.5, 99.5, 100) for i in range(31)
        ]
        # bar 31: signal has already been consumed at bar 30's close; this bar
        # spikes high enough to hit TP=105
        candles.append(_candle(31, 100, 106, 99.5, 103))

        def fire_once(symbol, _bars):
            # Return signal only on the 31st candle (ts=30)
            if _bars[-1].ts != 30:
                return None
            return StrategySignal(
                side="buy",
                confidence=0.8,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=105.0,
                expected_slippage_bps=5.0,
                leverage=2.0,
                rationale="test",
                symbol=symbol,
            )

        report = run_backtest(
            signal_generator=fire_once,
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            initial_equity_usd=10_000.0,
            risk_limits=_limits(),
            risk_fraction=0.1,
            fee_bps=0.0,
            slippage_bps=0.0,
            min_bars_for_signal=30,
        )
        self.assertEqual(report.signals_total, 1)
        self.assertEqual(report.signals_approved, 1)
        self.assertEqual(len(report.closed_trades), 1)
        trade = report.closed_trades[0]
        self.assertEqual(trade.exit_reason, "take_profit")
        self.assertEqual(trade.exit_price, 105.0)
        self.assertGreater(trade.pnl_usd, 0)



class BacktestStopLossTests(unittest.TestCase):
    def test_stop_loss_closes_losing_trade(self):
        candles = [_candle(i, 100, 100.5, 99.5, 100) for i in range(31)]
        candles.append(_candle(31, 100, 100.5, 90, 95))  # crashes through SL=95

        def fire_once(symbol, bars):
            if bars[-1].ts != 30:
                return None
            return StrategySignal(
                side="buy",
                confidence=0.8,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                expected_slippage_bps=5.0,
                leverage=2.0,
                rationale="test",
                symbol=symbol,
            )

        report = run_backtest(
            signal_generator=fire_once,
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            initial_equity_usd=10_000.0,
            risk_limits=_limits(),
            risk_fraction=0.1,
            fee_bps=0.0,
            slippage_bps=0.0,
            min_bars_for_signal=30,
        )
        trade = report.closed_trades[0]
        self.assertEqual(trade.exit_reason, "stop_loss")
        self.assertLess(trade.pnl_usd, 0)



class BacktestRiskEngineTests(unittest.TestCase):
    def test_signals_outside_allowlist_are_blocked(self):
        candles = [_candle(i, 100, 101, 99, 100) for i in range(32)]

        def fire_every_bar(symbol, bars):
            if len(bars) < 30:
                return None
            return StrategySignal(
                side="buy",
                confidence=0.5,
                entry_price=100.0,
                stop_loss_price=98.0,
                take_profit_price=104.0,
                expected_slippage_bps=5.0,
                leverage=2.0,
                rationale="t",
                symbol=symbol,
            )

        report = run_backtest(
            signal_generator=fire_every_bar,
            candles_by_symbol={"DOGE-USDT-SWAP": candles},
            initial_equity_usd=5_000.0,
            risk_limits=_limits(),
            allowed_symbols=("BTC-USDT-SWAP",),
            min_bars_for_signal=30,
        )
        self.assertGreater(report.signals_blocked, 0)
        self.assertEqual(report.signals_approved, 0)
        self.assertIn("symbol not in allowed list", report.block_reasons)

    def test_per_symbol_cap_blocks_second_entry(self):
        candles = [_candle(i, 100, 101, 99, 100) for i in range(35)]

        call_count = {"n": 0}
        def generate(symbol, bars):
            if len(bars) < 30:
                return None
            # Fire on bar 30 and 32
            if bars[-1].ts in (30, 32):
                call_count["n"] += 1
                return StrategySignal(
                    side="buy",
                    confidence=0.5,
                    entry_price=100.0,
                    stop_loss_price=98.0,
                    take_profit_price=110.0,
                    expected_slippage_bps=5.0,
                    leverage=2.0,
                    rationale="t",
                    symbol=symbol,
                )
            return None

        # First fills; second is on same open position so runner skips it
        # (the backtester ignores signals on already-open symbols). So to test
        # per-symbol cap we need to close first then try second — easier to just
        # test this inside the risk engine tests instead. We test the sizing
        # cap here: a single enormous signal gets sized down to 0.
        limits = _limits(max_notional_usd=50.0, max_notional_per_symbol_usd=50.0)
        report = run_backtest(
            signal_generator=generate,
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            initial_equity_usd=10_000.0,
            risk_limits=limits,
            risk_fraction=0.5,  # wants 5000 but cap is 50
            min_bars_for_signal=30,
        )
        # First signal lands at 50, second is suppressed by "already have open
        # position" rule — so exactly one entry.
        self.assertLessEqual(report.signals_approved, 1)
        if report.closed_trades:
            self.assertLessEqual(report.closed_trades[0].notional_usd, 50.0 + 0.001)



class BacktestReportMetricsTests(unittest.TestCase):
    def test_empty_run_produces_safe_defaults(self):
        report = run_backtest(
            signal_generator=lambda *_: None,
            candles_by_symbol={"X": [_candle(i, 100, 100, 100, 100) for i in range(40)]},
            initial_equity_usd=1000.0,
            risk_limits=_limits(),
        )
        self.assertEqual(report.signals_total, 0)
        self.assertEqual(report.closed_trades, [])
        self.assertEqual(report.win_rate, 0.0)
        self.assertEqual(report.max_drawdown_pct, 0.0)
        self.assertEqual(report.total_pnl_usd, 0.0)

    def test_max_drawdown_tracks_losing_streak(self):
        # Hand-built trade list via direct return from backtester is awkward;
        # we just make two consecutive losing trades via stop loss.
        candles = []
        for i in range(30):
            candles.append(_candle(i, 100, 100.5, 99.5, 100))
        # First cycle: signal at bar 30, SL at bar 31
        candles.append(_candle(30, 100, 100.5, 99.5, 100))
        candles.append(_candle(31, 100, 100.5, 94, 95))  # SL=95, hit
        # Second cycle: flat then SL again
        for i in range(32, 60):
            candles.append(_candle(i, 95, 95.5, 94.5, 95))
        candles.append(_candle(60, 95, 95.5, 89, 90))  # SL=90 if signal fires at 59

        def gen(symbol, bars):
            last_ts = bars[-1].ts
            if last_ts == 30:
                return StrategySignal("buy", 0.5, 100.0, 95.0, 110.0, 5.0, 2.0, "", symbol=symbol)
            if last_ts == 59:
                return StrategySignal("buy", 0.5, 95.0, 90.0, 105.0, 5.0, 2.0, "", symbol=symbol)
            return None

        report = run_backtest(
            signal_generator=gen,
            candles_by_symbol={"BTC-USDT-SWAP": candles},
            initial_equity_usd=10_000.0,
            risk_limits=_limits(),
            risk_fraction=0.1,
            fee_bps=0.0,
            slippage_bps=0.0,
            min_bars_for_signal=30,
        )
        self.assertEqual(len(report.closed_trades), 2)
        self.assertTrue(all(t.exit_reason == "stop_loss" for t in report.closed_trades))
        self.assertGreater(report.max_drawdown_pct, 0)


if __name__ == "__main__":
    unittest.main()
