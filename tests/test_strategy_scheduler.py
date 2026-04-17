import asyncio
import unittest

from agent_trader.strategy_scheduler import StrategyScheduler


class StrategySchedulerTests(unittest.TestCase):
    def test_run_cycle_invokes_runner_and_tracks_result(self):
        calls = []
        def runner():
            calls.append(1)
            return {"status": "ok", "count": len(calls)}
        scheduler = StrategyScheduler(runner=runner, poll_interval_seconds=60)
        result = asyncio.run(scheduler.run_cycle())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(scheduler.cycles_run, 1)
        self.assertEqual(scheduler.last_result["count"], 1)

    def test_run_forever_stops_when_should_continue_false(self):
        ticks = {"n": 0}
        def runner():
            ticks["n"] += 1
            return {"status": "ok"}
        sleep_calls = []
        async def fake_sleep(seconds):
            sleep_calls.append(seconds)
        def should_continue():
            return ticks["n"] < 3
        scheduler = StrategyScheduler(runner=runner, poll_interval_seconds=42)
        asyncio.run(scheduler.run_forever(should_continue=should_continue, sleep_fn=fake_sleep))
        self.assertEqual(ticks["n"], 3)
        self.assertEqual(scheduler.cycles_run, 3)
        self.assertEqual(sleep_calls, [42, 42, 42])

    def test_runner_exception_does_not_break_loop(self):
        ticks = {"n": 0}
        def runner():
            ticks["n"] += 1
            if ticks["n"] == 1:
                raise RuntimeError("transient fetch error")
            return {"status": "ok"}
        async def fake_sleep(_s):
            return None
        def should_continue():
            return ticks["n"] < 2
        scheduler = StrategyScheduler(runner=runner, poll_interval_seconds=1)
        asyncio.run(scheduler.run_forever(should_continue=should_continue, sleep_fn=fake_sleep))
        self.assertEqual(ticks["n"], 2)
        # only the successful cycle increments cycles_run
        self.assertEqual(scheduler.cycles_run, 1)


if __name__ == "__main__":
    unittest.main()
