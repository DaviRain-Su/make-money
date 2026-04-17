import unittest

from agent_trader.models import StrategySignal
from agent_trader.strategy import EmaAtrConfig
from agent_trader.strategy_runner import run_strategy_once


class FakeClient:
    def __init__(self, data):
        self._data = data
        self.calls = 0

    def get_candles(self, symbol, bar="1H", limit="100"):
        self.calls += 1
        return {"code": "0", "data": list(reversed(self._data))}


def _flat_rows(n: int = 60):
    return [[str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"] for i in range(n)]


class RunnerWithInjectedGeneratorTests(unittest.TestCase):
    def test_injected_generator_bypasses_default(self):
        def always_buy(symbol, candles, higher_tf=None):
            return StrategySignal(
                side="buy",
                confidence=1.0,
                entry_price=candles[-1].close,
                stop_loss_price=candles[-1].close * 0.98,
                take_profit_price=candles[-1].close * 1.03,
                expected_slippage_bps=5.0,
                leverage=1.0,
                rationale="always_buy_test",
                symbol=symbol,
            )
        client = FakeClient(_flat_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            signal_generator=always_buy,
        )
        self.assertEqual(results[0]["status"], "dispatched")
        self.assertEqual(results[0]["side"], "buy")
        self.assertEqual(dispatched[0]["rationale"], "always_buy_test")

    def test_none_returning_generator_produces_no_signal(self):
        client = FakeClient(_flat_rows())
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda _p: {},
            signal_generator=lambda *_a, **_kw: None,
        )
        self.assertEqual(results[0]["status"], "no_signal")


if __name__ == "__main__":
    unittest.main()
