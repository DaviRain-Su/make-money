import asyncio
import unittest

from agent_trader.reconcile_scheduler import ReconcileScheduler


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, open_orders):
        self.calls.append(list(open_orders))
        return {"results": [{"status": "filled"}], "count": len(open_orders)}


class ReconcileSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_cycle_invokes_runner_with_open_orders(self):
        runner = FakeRunner()
        scheduler = ReconcileScheduler(runner=runner, poll_interval_seconds=30)

        result = await scheduler.run_cycle([
            {"symbol": "BTC-USDT-SWAP", "order_id": "1"}
        ])

        self.assertEqual(runner.calls, [[{"symbol": "BTC-USDT-SWAP", "order_id": "1"}]])
        self.assertEqual(result["count"], 1)
        self.assertEqual(scheduler.last_result["results"][0]["status"], "filled")

    async def test_run_forever_stops_when_should_continue_returns_false(self):
        runner = FakeRunner()
        scheduler = ReconcileScheduler(runner=runner, poll_interval_seconds=1)
        should_continue = iter([True, False]).__next__
        snapshots = iter([
            [{"symbol": "BTC-USDT-SWAP", "order_id": "1"}],
            []
        ]).__next__

        await scheduler.run_forever(load_open_orders=snapshots, should_continue=should_continue, sleep_fn=lambda _: asyncio.sleep(0))

        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(scheduler.cycles_run, 1)


if __name__ == "__main__":
    unittest.main()
