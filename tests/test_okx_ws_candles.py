import unittest

from agent_trader.okx_ws_candles import (
    CandleStreamListener,
    build_candle_subscription_args,
    parse_candle_push,
)
from agent_trader.strategy import Candle


def _candle_msg(symbol: str, bar: str, rows):
    return {"arg": {"channel": f"candle{bar}", "instId": symbol}, "data": rows}


class BuildSubscriptionArgsTests(unittest.TestCase):
    def test_single_symbol(self):
        args = build_candle_subscription_args(["BTC-USDT-SWAP"], "1H")
        self.assertEqual(args, [{"channel": "candle1H", "instId": "BTC-USDT-SWAP"}])

    def test_multiple_symbols_and_skips_empty(self):
        args = build_candle_subscription_args(["A", "", "B"], "5m")
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0]["channel"], "candle5m")
        self.assertEqual(args[1]["instId"], "B")


class ParseCandlePushTests(unittest.TestCase):
    def test_extracts_confirmed_flag(self):
        msg = _candle_msg(
            "BTC-USDT-SWAP", "1H",
            [["1700000000000", "100", "101", "99", "100.5", "1", "", "", "1"]],
        )
        out = parse_candle_push(msg)
        self.assertEqual(len(out), 1)
        sym, bar, candle, confirmed = out[0]
        self.assertEqual(sym, "BTC-USDT-SWAP")
        self.assertEqual(bar, "1H")
        self.assertTrue(confirmed)
        self.assertEqual(candle.close, 100.5)

    def test_unconfirmed_flag_is_preserved(self):
        msg = _candle_msg(
            "BTC-USDT-SWAP", "1H",
            [["1700000000000", "100", "101", "99", "100.5", "1", "", "", "0"]],
        )
        _s, _b, _c, confirmed = parse_candle_push(msg)[0]
        self.assertFalse(confirmed)

    def test_non_candle_message_ignored(self):
        self.assertEqual(parse_candle_push({"arg": {"channel": "orders"}, "data": []}), [])
        self.assertEqual(parse_candle_push({}), [])

    def test_malformed_rows_are_skipped(self):
        msg = _candle_msg("BTC-USDT-SWAP", "1H", [["bad"], [], ["1", "x", "y", "z", "w"]])
        self.assertEqual(parse_candle_push(msg), [])


class CandleStreamListenerTests(unittest.TestCase):
    def test_fires_callback_only_on_newly_confirmed(self):
        received = []
        listener = CandleStreamListener(
            on_confirmed=lambda sym, bar, candle: received.append((sym, bar, candle.ts))
        )
        # forming
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["1000", "100", "101", "99", "100", "1", "", "", "0"]]))
        # confirmed
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["1000", "100", "101", "99", "100.5", "1", "", "", "1"]]))
        # confirmed again (duplicate push, same ts)
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["1000", "100", "101", "99", "100.5", "1", "", "", "1"]]))
        # newer confirmed
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["2000", "100", "102", "99", "101", "1", "", "", "1"]]))
        self.assertEqual(received, [("BTC-USDT-SWAP", "1H", 1000), ("BTC-USDT-SWAP", "1H", 2000)])

    def test_callback_exception_swallowed(self):
        listener = CandleStreamListener(
            on_confirmed=lambda *_a: (_ for _ in ()).throw(RuntimeError("bad handler"))
        )
        # must not raise
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["1000", "100", "101", "99", "100", "1", "", "", "1"]]))

    def test_keys_by_symbol_and_bar_independently(self):
        received = []
        listener = CandleStreamListener(
            on_confirmed=lambda s, b, c: received.append((s, b, c.ts))
        )
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "1H", [["1000", "100", "101", "99", "100", "1", "", "", "1"]]))
        listener.on_message(_candle_msg("BTC-USDT-SWAP", "5m", [["1000", "100", "101", "99", "100", "1", "", "", "1"]]))
        self.assertEqual(len(received), 2)


if __name__ == "__main__":
    unittest.main()
