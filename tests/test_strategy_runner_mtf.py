import unittest

from agent_trader.strategy import EmaAtrConfig
from agent_trader.strategy_runner import run_strategy_once


def _flat_then_trigger_rows():
    rows = []
    for i in range(60):
        rows.append([str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"])
    rows.append([str(60 * 1000), "110", "111", "109", "110", "1", "", "", "1"])
    return rows


def _rising_htf_rows():
    rows = []
    for i in range(80):
        price = 100 + i
        rows.append([str(i * 1_000_000), str(price), str(price + 1), str(price - 1), str(price), "1", "", "", "1"])
    return rows


def _flat_htf_rows():
    rows = []
    for i in range(80):
        rows.append([str(i * 1_000_000), "100", "101", "99", "100", "1", "", "", "1"])
    return rows


class MultiCandleFetchClient:
    def __init__(self, primary, htf):
        self.primary = primary
        self.htf = htf
        self.calls = []

    def get_candles(self, symbol, bar="1H", limit="100"):
        self.calls.append((symbol, bar, limit))
        rows = self.htf if bar == "4H" else self.primary
        return {"code": "0", "data": list(reversed(rows))}


class RunnerMultiTimeframeTests(unittest.TestCase):
    def setUp(self):
        self.config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=20)

    def test_runner_fetches_higher_tf_and_dispatches_when_trend_agrees(self):
        client = MultiCandleFetchClient(_flat_then_trigger_rows(), _rising_htf_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=100,
            strategy_config=self.config,
            dispatch=lambda payload: dispatched.append(payload) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            higher_tf_bar="4H",
        )
        # Two OKX calls: primary + higher-tf
        self.assertEqual(len(client.calls), 2)
        bars_called = {c[1] for c in client.calls}
        self.assertIn("1H", bars_called)
        self.assertIn("4H", bars_called)
        self.assertEqual(results[0]["status"], "dispatched")
        self.assertEqual(results[0]["side"], "buy")

    def test_runner_returns_no_signal_when_trend_disagrees(self):
        client = MultiCandleFetchClient(_flat_then_trigger_rows(), _flat_htf_rows())
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=100,
            strategy_config=self.config,
            dispatch=lambda _p: {},
            higher_tf_bar="4H",
        )
        self.assertEqual(results[0]["status"], "no_signal")

    def test_runner_skips_htf_fetch_when_filter_disabled(self):
        client = MultiCandleFetchClient(_flat_then_trigger_rows(), _flat_htf_rows())
        config = EmaAtrConfig(fast_ema=5, slow_ema=20, atr_period=14, higher_tf_slow_ema=0)
        run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=100,
            strategy_config=config,
            dispatch=lambda _p: {"risk": {"approved": True}, "execution": {"status": "paper"}},
            higher_tf_bar="4H",  # supplied but filter is off → should be ignored
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][1], "1H")


if __name__ == "__main__":
    unittest.main()
