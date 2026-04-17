import unittest

from agent_trader.strategy import Candle, EmaAtrConfig, generate_ema_atr_signal


def _flat(n: int, price: float = 100.0) -> list:
    return [Candle(ts=i * 1000, open=price, high=price + 0.5, low=price - 0.5, close=price) for i in range(n)]


def _spike(ts: int, price: float) -> Candle:
    return Candle(ts=ts, open=price, high=price + 1, low=price - 1, close=price)


def _make_primary_buy_crossover():
    """60 flat + 1 trigger bar that produces a buy crossover on the last bar."""
    candles = _flat(60, price=100)
    candles.append(_spike(60_000, 110))
    return candles


class MultiTimeframeFilterTests(unittest.TestCase):
    def test_disabled_filter_still_emits_signal(self):
        candles = _make_primary_buy_crossover()
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=0)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, config)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "buy")

    def test_enabled_filter_blocks_when_higher_tf_missing(self):
        candles = _make_primary_buy_crossover()
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=20)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, config, higher_tf_candles=None)
        self.assertIsNone(sig)

    def test_filter_rejects_buy_when_higher_tf_trend_flat(self):
        candles = _make_primary_buy_crossover()
        # Flat higher timeframe: slow EMA slope ≈ 0, should reject
        htf_flat = _flat(80, price=100)
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=20)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, config, higher_tf_candles=htf_flat)
        self.assertIsNone(sig)

    def test_filter_accepts_buy_when_higher_tf_trends_up(self):
        candles = _make_primary_buy_crossover()
        # Rising higher timeframe → slow EMA is still climbing at the last bar
        htf_rising = [
            Candle(ts=i * 1000, open=100 + i, high=100 + i + 1, low=100 + i - 1, close=100 + i)
            for i in range(80)
        ]
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=20)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, config, higher_tf_candles=htf_rising)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "buy")

    def test_filter_rejects_buy_when_higher_tf_trends_down(self):
        candles = _make_primary_buy_crossover()
        # Higher timeframe falling → reject long
        htf_falling = [
            Candle(ts=i * 1000, open=200 - i, high=200 - i + 1, low=200 - i - 1, close=200 - i)
            for i in range(80)
        ]
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=20)
        sig = generate_ema_atr_signal("BTC-USDT-SWAP", candles, config, higher_tf_candles=htf_falling)
        self.assertIsNone(sig)


if __name__ == "__main__":
    unittest.main()
