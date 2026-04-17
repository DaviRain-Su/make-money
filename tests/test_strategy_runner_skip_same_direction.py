import unittest

from agent_trader.models import StrategySignal
from agent_trader.strategy import EmaAtrConfig
from agent_trader.strategy_runner import run_strategy_once


def _flat_rows(n: int = 60):
    return [[str(i * 1000), "100", "101", "99", "100", "1", "", "", "1"] for i in range(n)]


class FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def get_candles(self, symbol, bar="1H", limit="200"):
        return {"code": "0", "data": list(reversed(self.rows))}


def _always(side: str):
    def gen(symbol, candles, higher_tf=None):
        return StrategySignal(
            side=side,
            confidence=1.0,
            entry_price=candles[-1].close,
            stop_loss_price=candles[-1].close * 0.98,
            take_profit_price=candles[-1].close * 1.03,
            expected_slippage_bps=5.0,
            leverage=1.0,
            rationale="test",
            symbol=symbol,
        )
    return gen


class SkipSameDirectionTests(unittest.TestCase):
    def test_skips_buy_when_long_already_open(self):
        client = FakeClient(_flat_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {},
            signal_generator=_always("buy"),
            open_direction_by_symbol={"BTC-USDT-SWAP": "long"},
        )
        self.assertEqual(results[0]["status"], "same_direction_open_position")
        self.assertEqual(results[0]["open_direction"], "long")
        self.assertEqual(dispatched, [])

    def test_skips_sell_when_short_already_open(self):
        client = FakeClient(_flat_rows())
        results = run_strategy_once(
            client=client,
            symbols=["ETH-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda _p: {},
            signal_generator=_always("sell"),
            open_direction_by_symbol={"ETH-USDT-SWAP": "short"},
        )
        self.assertEqual(results[0]["status"], "same_direction_open_position")

    def test_allows_opposite_direction_to_fire(self):
        client = FakeClient(_flat_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            signal_generator=_always("sell"),
            open_direction_by_symbol={"BTC-USDT-SWAP": "long"},
        )
        self.assertEqual(results[0]["status"], "dispatched")
        self.assertEqual(results[0]["side"], "sell")
        self.assertEqual(len(dispatched), 1)

    def test_allows_dispatch_when_symbol_not_in_map(self):
        client = FakeClient(_flat_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["SOL-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            signal_generator=_always("buy"),
            open_direction_by_symbol={"BTC-USDT-SWAP": "long"},
        )
        self.assertEqual(results[0]["status"], "dispatched")

    def test_none_map_disables_feature(self):
        client = FakeClient(_flat_rows())
        dispatched = []
        results = run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            signal_generator=_always("buy"),
            open_direction_by_symbol=None,
        )
        self.assertEqual(results[0]["status"], "dispatched")


if __name__ == "__main__":
    unittest.main()
