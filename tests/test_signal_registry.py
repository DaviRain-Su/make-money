import unittest

from agent_trader.models import StrategySignal
from agent_trader.signal_registry import available, register, register_ema_atr, resolve, unregister
from agent_trader.strategy import Candle


class SignalRegistryTests(unittest.TestCase):
    def tearDown(self):
        # Keep global state clean across tests
        unregister("test_custom")

    def test_ema_atr_is_registered_by_default(self):
        self.assertIn("ema_atr", available())

    def test_resolve_unknown_raises(self):
        with self.assertRaises(KeyError):
            resolve("nope_no_way")

    def test_custom_generator_can_be_registered_and_resolved(self):
        def custom(symbol, candles, higher_tf=None):
            return StrategySignal(
                side="buy",
                confidence=1.0,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                expected_slippage_bps=5.0,
                leverage=1.0,
                rationale="custom",
                symbol=symbol,
            )
        register("test_custom", custom)
        generator = resolve("test_custom")
        sig = generator("BTC-USDT-SWAP", [Candle(ts=0, open=1, high=1, low=1, close=1)])
        self.assertEqual(sig.rationale, "custom")
        self.assertEqual(sig.symbol, "BTC-USDT-SWAP")

    def test_register_ema_atr_allows_named_variants(self):
        from agent_trader.strategy import EmaAtrConfig
        register_ema_atr("slow_ema_atr", EmaAtrConfig(fast_ema=50, slow_ema=200))
        self.assertIn("slow_ema_atr", available())
        unregister("slow_ema_atr")
        self.assertNotIn("slow_ema_atr", available())

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            register("", lambda *_: None)


if __name__ == "__main__":
    unittest.main()
