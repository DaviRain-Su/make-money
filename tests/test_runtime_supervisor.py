import asyncio
import unittest

from agent_trader.runtime_supervisor import RuntimeSupervisor


class FakeManager:
    def __init__(self):
        self.run_once_calls = []
        self.reconnect_calls = []
        self.fail_once = False

    async def run_once(self, timestamp, send_ping=False):
        self.run_once_calls.append((timestamp, send_ping))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("boom")
        return {"ok": True}

    async def reconnect_async(self, websocket, timestamp):
        self.reconnect_calls.append((websocket, timestamp))


class FakeScheduler:
    def __init__(self):
        self.cycles = []

    async def run_cycle(self, open_orders):
        self.cycles.append(list(open_orders))
        return {"count": len(open_orders)}


class RuntimeSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_iteration_calls_ws_and_scheduler(self):
        manager = FakeManager()
        scheduler = FakeScheduler()
        supervisor = RuntimeSupervisor(
            ws_manager=manager,
            reconcile_scheduler=scheduler,
            timestamp_fn=lambda: "1700000000",
        )

        result = await supervisor.run_iteration(
            load_open_orders=lambda: [{"symbol": "BTC-USDT-SWAP", "order_id": "1"}],
            send_ping=True,
        )

        self.assertEqual(manager.run_once_calls, [("1700000000", True)])
        self.assertEqual(scheduler.cycles, [[{"symbol": "BTC-USDT-SWAP", "order_id": "1"}]])
        self.assertEqual(result["scheduler"]["count"], 1)

    async def test_run_iteration_reconnects_on_ws_failure(self):
        manager = FakeManager()
        manager.fail_once = True
        scheduler = FakeScheduler()
        supervisor = RuntimeSupervisor(
            ws_manager=manager,
            reconcile_scheduler=scheduler,
            timestamp_fn=lambda: "1700000001",
            websocket_factory=lambda: "new-ws",
        )

        result = await supervisor.run_iteration(load_open_orders=lambda: [], send_ping=False)

        self.assertEqual(manager.reconnect_calls, [("new-ws", "1700000001")])
        self.assertEqual(result["ws_error"], "boom")

    async def test_run_forever_stops_when_predicate_turns_false(self):
        manager = FakeManager()
        scheduler = FakeScheduler()
        supervisor = RuntimeSupervisor(
            ws_manager=manager,
            reconcile_scheduler=scheduler,
            timestamp_fn=lambda: "1700000002",
        )
        keep = iter([True, False]).__next__

        await supervisor.run_forever(
            load_open_orders=lambda: [],
            should_continue=keep,
            sleep_fn=lambda _: asyncio.sleep(0),
            send_ping=False,
        )

        self.assertEqual(supervisor.iterations_run, 1)
        self.assertEqual(len(manager.run_once_calls), 1)


if __name__ == "__main__":
    unittest.main()
