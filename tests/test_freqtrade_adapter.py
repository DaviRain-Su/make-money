import unittest

from agent_trader.freqtrade_adapter import pair_to_instid, translate_freqtrade_webhook


class PairMappingTests(unittest.TestCase):
    def test_spot_pair_becomes_swap(self):
        self.assertEqual(pair_to_instid("BTC/USDT"), "BTC-USDT-SWAP")

    def test_freqtrade_futures_syntax(self):
        self.assertEqual(pair_to_instid("ETH/USDT:USDT"), "ETH-USDT-SWAP")

    def test_okx_native_passthrough(self):
        self.assertEqual(pair_to_instid("SOL-USDT-SWAP"), "SOL-USDT-SWAP")

    def test_lowercase_normalized(self):
        self.assertEqual(pair_to_instid("btc/usdt"), "BTC-USDT-SWAP")


class EntryTranslationTests(unittest.TestCase):
    def test_long_entry_with_explicit_sl(self):
        body = {
            "type": "entry",
            "trade_id": 42,
            "pair": "BTC/USDT",
            "direction": "long",
            "open_rate": 50000,
            "leverage": 3,
            "stop_loss": 49000,
            "enter_tag": "ema_cross",
        }
        out = translate_freqtrade_webhook(body)
        self.assertEqual(out["side"], "buy")
        self.assertEqual(out["symbol"], "BTC-USDT-SWAP")
        self.assertEqual(out["entry_price"], 50000)
        self.assertEqual(out["stop_loss_price"], 49000)
        # TP defaults to 3R: distance=1000 → TP=53000
        self.assertEqual(out["take_profit_price"], 53000)
        self.assertEqual(out["position_action"], "OPEN")
        self.assertEqual(out["leverage"], 3.0)
        self.assertEqual(out["client_signal_id"], "freqtrade:42:OPEN:BTC-USDT-SWAP:buy")
        self.assertIn("ema_cross", out["rationale"])

    def test_short_entry_without_stop_uses_fallback_pct(self):
        body = {
            "pair": "ETH/USDT:USDT",
            "direction": "short",
            "open_rate": 3000,
            "trade_id": 7,
        }
        out = translate_freqtrade_webhook(body, fallback_stop_pct=0.02)
        self.assertEqual(out["side"], "sell")
        self.assertEqual(out["symbol"], "ETH-USDT-SWAP")
        # Short: stop sits above entry by 2% → 3060
        self.assertAlmostEqual(out["stop_loss_price"], 3060.0)
        # TP = 3000 - 3 * 60 = 2820
        self.assertAlmostEqual(out["take_profit_price"], 2820.0)

    def test_stop_loss_pct_is_used_when_price_absent(self):
        body = {
            "pair": "BTC/USDT",
            "direction": "long",
            "open_rate": 100,
            "stop_loss_pct": -0.05,
            "trade_id": 1,
        }
        out = translate_freqtrade_webhook(body)
        self.assertAlmostEqual(out["stop_loss_price"], 95.0)

    def test_leverage_floors_at_one(self):
        body = {
            "pair": "BTC/USDT",
            "direction": "long",
            "open_rate": 100,
            "leverage": 0,
            "trade_id": 1,
        }
        out = translate_freqtrade_webhook(body)
        self.assertEqual(out["leverage"], 1.0)


class ExitTranslationTests(unittest.TestCase):
    def test_long_exit_becomes_close_sell(self):
        body = {
            "type": "exit",
            "trade_id": 42,
            "pair": "BTC/USDT",
            "direction": "long",
            "close_rate": 51000,
            "exit_reason": "roi",
        }
        out = translate_freqtrade_webhook(body)
        self.assertEqual(out["position_action"], "CLOSE")
        self.assertEqual(out["side"], "sell")
        self.assertEqual(out["entry_price"], 51000)
        self.assertEqual(out["client_signal_id"], "freqtrade:42:CLOSE:BTC-USDT-SWAP:sell")
        self.assertIn("roi", out["rationale"])

    def test_short_exit_becomes_close_buy(self):
        body = {
            "type": "exit",
            "trade_id": 99,
            "pair": "ETH/USDT",
            "direction": "short",
            "close_rate": 2900,
            "exit_reason": "stop_loss",
        }
        out = translate_freqtrade_webhook(body)
        self.assertEqual(out["position_action"], "CLOSE")
        self.assertEqual(out["side"], "buy")


class ValidationTests(unittest.TestCase):
    def test_missing_pair_raises(self):
        with self.assertRaises(ValueError):
            translate_freqtrade_webhook({"direction": "long", "open_rate": 100})

    def test_missing_price_raises(self):
        with self.assertRaises(ValueError):
            translate_freqtrade_webhook({"pair": "BTC/USDT", "direction": "long"})

    def test_unknown_direction_raises(self):
        with self.assertRaises(ValueError):
            translate_freqtrade_webhook({"pair": "BTC/USDT", "direction": "sideways", "open_rate": 100})


if __name__ == "__main__":
    unittest.main()
