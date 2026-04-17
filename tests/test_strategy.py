import unittest

from agent_trader.strategy import (
    Candle,
    EmaAtrConfig,
    compute_atr,
    compute_ema,
    generate_ema_atr_signal,
    parse_okx_candles,
)


def _candle(ts: int, price: float, high_boost: float = 1.0, low_drop: float = 1.0) -> Candle:
    return Candle(
        ts=ts,
        open=price,
        high=price + high_boost,
        low=price - low_drop,
        close=price,
    )


class EMATests(unittest.TestCase):
    def test_returns_none_before_window(self):
        out = compute_ema([1, 2, 3], period=5)
        self.assertEqual(out, [None, None, None])

    def test_first_ema_equals_seed_sma(self):
        values = [1, 2, 3, 4, 5]
        out = compute_ema(values, period=3)
        self.assertIsNone(out[0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[2], 2.0)  # SMA of first 3

    def test_ema_reacts_to_new_high(self):
        values = [10] * 20 + [20]
        out = compute_ema(values, period=5)
        self.assertLess(out[19], out[20])


class ATRTests(unittest.TestCase):
    def test_returns_none_when_not_enough_bars(self):
        out = compute_atr([_candle(i, 100) for i in range(5)], period=10)
        self.assertTrue(all(v is None for v in out))

    def test_atr_converges_on_steady_range(self):
        # All candles with consistent 2-unit range should give ATR ≈ 2
        candles = [_candle(i, 100 + i * 0.0, high_boost=1.0, low_drop=1.0) for i in range(30)]
        out = compute_atr(candles, period=14)
        self.assertIsNotNone(out[14])
        self.assertAlmostEqual(out[29], 2.0, places=1)


class EMAATRSignalTests(unittest.TestCase):
    def _build_crossover_candles(self, flip_up: bool) -> list:
        # 60 flat bars to stabilize both EMAs near the same value, then one
        # decisive bar that forces a fast-vs-slow crossover *on the last bar*.
        candles = []
        base = 100.0
        for i in range(60):
            candles.append(_candle(i * 1000, base))
        # Trigger bar: large move in flip_up direction — pushes fast EMA past slow
        trigger_price = base + 10.0 if flip_up else base - 10.0
        candles.append(_candle(60 * 1000, trigger_price))
        return candles

    def test_buy_signal_on_upward_crossover(self):
        candles = self._build_crossover_candles(flip_up=True)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14))
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "buy")
        self.assertEqual(sig.symbol, "BTC-USDT-SWAP")
        self.assertGreater(sig.take_profit_price, sig.entry_price)
        self.assertLess(sig.stop_loss_price, sig.entry_price)

    def test_sell_signal_on_downward_crossover(self):
        candles = self._build_crossover_candles(flip_up=False)
        sig = generate_ema_atr_signal("ETH-USDT-SWAP", candles, EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14))
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "sell")
        self.assertLess(sig.take_profit_price, sig.entry_price)
        self.assertGreater(sig.stop_loss_price, sig.entry_price)

    def test_no_signal_without_crossover(self):
        # Steady uptrend without any crossover in the last bar
        candles = [_candle(i * 1000, 100 + i * 0.1) for i in range(100)]
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14))
        self.assertIsNone(sig)

    def test_no_signal_when_not_enough_bars(self):
        candles = [_candle(i * 1000, 100 + i) for i in range(10)]
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14))
        self.assertIsNone(sig)


class OKXCandleParseTests(unittest.TestCase):
    def test_parse_okx_candles_drops_unconfirmed_and_sorts_oldest_first(self):
        response = {
            "data": [
                ["1700000600000", "102", "103", "101", "102.5", "10", "", "", "0"],  # unconfirmed
                ["1700000500000", "101", "102", "100", "101.5", "12", "", "", "1"],
                ["1700000400000", "100", "101", "99", "100.5", "15", "", "", "1"],
            ]
        }
        candles = parse_okx_candles(response)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].ts, 1700000400000)
        self.assertEqual(candles[1].ts, 1700000500000)
        self.assertEqual(candles[1].close, 101.5)

    def test_parse_okx_candles_include_unconfirmed(self):
        response = {
            "data": [
                ["1700000600000", "102", "103", "101", "102.5", "10", "", "", "0"],
                ["1700000500000", "101", "102", "100", "101.5", "12", "", "", "1"],
            ]
        }
        candles = parse_okx_candles(response, include_unconfirmed=True)
        self.assertEqual(len(candles), 2)

    def test_parse_okx_candles_handles_empty_and_bad_rows(self):
        response = {"data": [["badrow"], [], ["1700000500000", "a", "b", "c", "d", "", "", "", "1"]]}
        self.assertEqual(parse_okx_candles(response), [])


if __name__ == "__main__":
    unittest.main()
