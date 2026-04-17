import unittest

from agent_trader.strategy import Candle, EmaAtrConfig
from agent_trader.strategy_runner import run_strategy_once


def _uptrend_candles() -> list:
    # 60 flat + 1 trigger bar (buy crossover on last bar)
    rows = []
    for i in range(60):
        rows.append([str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"])
    rows.append([str(60 * 1000), "110", "111", "109", "110", "1", "", "", "1"])
    return rows


class FakeClient:
    def __init__(self, data_by_symbol):
        self._data = data_by_symbol
        self.calls = []

    def get_candles(self, symbol, bar="1H", limit="200"):
        self.calls.append((symbol, bar, limit))
        rows = self._data.get(symbol, [])
        return {"code": "0", "data": list(reversed(rows))}  # OKX returns newest-first


class StrategyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14)

    def test_dispatches_signal_on_crossover(self):
        client = FakeClient({"BTC-USDT-SWAP": _uptrend_candles()})
        dispatched = []

        def sink(payload):
            dispatched.append(payload)
            return {"risk": {"approved": True}, "execution": {"status": "paper"}}

        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=200,
            strategy_config=self.config,
            dispatch=sink,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "dispatched")
        self.assertEqual(results[0]["side"], "buy")
        self.assertEqual(len(dispatched), 1)
        payload = dispatched[0]
        self.assertTrue(payload["client_signal_id"].startswith("ema_atr:BTC-USDT-SWAP:1H:"))
        self.assertEqual(payload["side"], "buy")

    def test_returns_no_signal_when_no_crossover(self):
        flat_rows = [
            [str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"]
            for i in range(80)
        ]
        client = FakeClient({"BTC-USDT-SWAP": flat_rows})
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=200,
            strategy_config=self.config,
            dispatch=lambda _p: {},
        )
        self.assertEqual(results[0]["status"], "no_signal")

    def test_duplicate_from_dispatcher_is_reported_gracefully(self):
        client = FakeClient({"BTC-USDT-SWAP": _uptrend_candles()})
        def sink(_payload):
            raise ValueError("duplicate signal")
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=200,
            strategy_config=self.config,
            dispatch=sink,
        )
        self.assertEqual(results[0]["status"], "duplicate")

    def test_fetch_error_is_captured_per_symbol(self):
        class BrokenClient:
            def get_candles(self, symbol, bar="1H", limit="200"):
                raise RuntimeError("network down")
        results = run_strategy_once(
            client=BrokenClient(),
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=200,
            strategy_config=self.config,
            dispatch=lambda _p: {},
        )
        self.assertEqual(results[0]["status"], "fetch_error")
        self.assertIn("network down", results[0]["error"])

    def test_multi_symbol_processed_independently(self):
        client = FakeClient(
            {
                "BTC-USDT-SWAP": _uptrend_candles(),
                "ETH-USDT-SWAP": [
                    [str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"]
                    for i in range(80)
                ],
            }
        )
        dispatched = []

        def sink(payload):
            dispatched.append(payload["symbol"])
            return {"risk": {"approved": True}, "execution": {"status": "paper"}}

        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            bar="1H",
            candle_limit=200,
            strategy_config=self.config,
            dispatch=sink,
        )
        self.assertEqual(results[0]["status"], "dispatched")
        self.assertEqual(results[1]["status"], "no_signal")
        self.assertEqual(dispatched, ["BTC-USDT-SWAP"])


if __name__ == "__main__":
    unittest.main()
