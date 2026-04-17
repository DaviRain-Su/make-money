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
            rationale="base",
            symbol=symbol,
        )
    return gen


class StrategyPullbackTests(unittest.TestCase):
    def test_close_only_converts_reverse_signal_to_close(self):
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
            reverse_signal_mode="close_only",
        )
        self.assertEqual(results[0]["status"], "dispatched")
        payload = dispatched[0]
        self.assertEqual(payload["position_action"], "CLOSE")
        self.assertIn("pullback_close", payload["rationale"])
        self.assertTrue(payload["client_signal_id"].endswith(":close"))

    def test_default_mode_allows_direct_flip(self):
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
            reverse_signal_mode="open",
        )
        self.assertEqual(results[0]["status"], "dispatched")
        payload = dispatched[0]
        self.assertEqual(payload["position_action"], "OPEN")
        self.assertTrue(payload["client_signal_id"].endswith(":open"))

    def test_close_only_with_no_position_is_normal_open(self):
        client = FakeClient(_flat_rows())
        dispatched = []
        run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: dispatched.append(p) or {"risk": {"approved": True}, "execution": {"status": "paper"}},
            signal_generator=_always("buy"),
            open_direction_by_symbol={},
            reverse_signal_mode="close_only",
        )
        self.assertEqual(dispatched[0]["position_action"], "OPEN")

    def test_client_signal_id_distinguishes_open_and_close(self):
        client = FakeClient(_flat_rows())
        open_payloads = []
        close_payloads = []
        run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: open_payloads.append(p) or {"execution": {"status": "paper"}},
            signal_generator=_always("buy"),
            open_direction_by_symbol={},
        )
        run_strategy_once(
            client=client,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            candle_limit=60,
            strategy_config=EmaAtrConfig(fast_ema=5, slow_ema=20),
            dispatch=lambda p: close_payloads.append(p) or {"execution": {"status": "paper"}},
            signal_generator=_always("sell"),
            open_direction_by_symbol={"BTC-USDT-SWAP": "long"},
            reverse_signal_mode="close_only",
        )
        self.assertNotEqual(open_payloads[0]["client_signal_id"], close_payloads[0]["client_signal_id"])


if __name__ == "__main__":
    unittest.main()
