import asyncio
import unittest

from agent_trader.candle_stream import OKXCandleStream, make_strategy_trigger


class FakeTransport:
    def __init__(self, messages, raise_on_nth_recv=None):
        self.sent = []
        self.messages = list(messages)
        self.connected = False
        self.closed = False
        self.recv_count = 0
        self.raise_on_nth_recv = raise_on_nth_recv

    async def connect(self):
        self.connected = True

    async def send(self, payload):
        self.sent.append(payload)

    async def recv(self):
        self.recv_count += 1
        if self.raise_on_nth_recv is not None and self.recv_count == self.raise_on_nth_recv:
            raise RuntimeError("transport dead")
        if not self.messages:
            # stay quiet; caller controls lifecycle via should_continue
            return None
        return self.messages.pop(0)

    async def close(self):
        self.closed = True
        self.connected = False


def _candle_msg(symbol, bar, ts, close, confirm="1"):
    return {
        "arg": {"channel": f"candle{bar}", "instId": symbol},
        "data": [[str(ts), "100", "101", "99", str(close), "1", "", "", confirm]],
    }


class OKXCandleStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_and_subscribe_sends_payload_once(self):
        transport = FakeTransport(messages=[])
        stream = OKXCandleStream(transport=transport, symbols=["BTC-USDT-SWAP"], bar="1H")
        await stream.connect_and_subscribe()
        await stream.connect_and_subscribe()  # idempotent
        self.assertTrue(transport.connected)
        self.assertEqual(len(transport.sent), 1)
        args = transport.sent[0]["args"]
        self.assertEqual(args, [{"channel": "candle1H", "instId": "BTC-USDT-SWAP"}])

    async def test_process_one_invokes_callback_on_confirmed(self):
        received = []
        transport = FakeTransport(messages=[
            _candle_msg("BTC-USDT-SWAP", "1H", 1000, 100, confirm="0"),
            _candle_msg("BTC-USDT-SWAP", "1H", 1000, 100.5, confirm="1"),
        ])
        stream = OKXCandleStream(
            transport=transport,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            on_confirmed=lambda s, b, c: received.append((s, b, c.ts, c.close)),
        )
        await stream.connect_and_subscribe()
        await stream.process_one()
        await stream.process_one()
        self.assertEqual(received, [("BTC-USDT-SWAP", "1H", 1000, 100.5)])

    async def test_run_forever_reconnects_on_transport_failure(self):
        transport = FakeTransport(
            messages=[_candle_msg("BTC-USDT-SWAP", "1H", 1000, 100.5, confirm="1")],
            raise_on_nth_recv=1,
        )
        iterations = {"n": 0}

        async def fake_sleep(_s):
            return None

        def should_continue():
            iterations["n"] += 1
            return iterations["n"] <= 2

        stream = OKXCandleStream(
            transport=transport,
            symbols=["BTC-USDT-SWAP"],
            bar="1H",
            reconnect_backoff_seconds=0.0,
            on_confirmed=lambda *_a: None,
        )
        await stream.run_forever(should_continue=should_continue, sleep_fn=fake_sleep)
        # first recv raised → close called → reconnect → second recv succeeded
        self.assertTrue(transport.closed)
        self.assertGreaterEqual(stream.messages_processed, 1)


class MakeStrategyTriggerTests(unittest.TestCase):
    def test_trigger_calls_runner_with_symbol_and_bar(self):
        calls = []
        trigger = make_strategy_trigger(lambda sym, bar: calls.append((sym, bar)))
        import types
        dummy_candle = types.SimpleNamespace(ts=1, close=100)
        trigger("BTC-USDT-SWAP", "1H", dummy_candle)
        self.assertEqual(calls, [("BTC-USDT-SWAP", "1H")])

    def test_trigger_swallows_runner_exception(self):
        def boom(*_a):
            raise RuntimeError("strategy exploded")
        trigger = make_strategy_trigger(boom)
        import types
        dummy_candle = types.SimpleNamespace(ts=1, close=100)
        # must not raise
        trigger("BTC-USDT-SWAP", "1H", dummy_candle)


if __name__ == "__main__":
    unittest.main()
