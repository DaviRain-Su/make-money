import asyncio
import unittest

from agent_trader.runtime_daemon import RuntimeDaemon


class FakeSupervisor:
    def __init__(self):
        self.calls = []
        self.fail_once = False

    async def run_iteration(self, load_open_orders, send_ping=False):
        self.calls.append({"send_ping": send_ping, "orders": load_open_orders()})
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("daemon boom")

    async def run_forever(self, load_open_orders, should_continue, sleep_fn, send_ping=False):
        self.calls.append({"send_ping": send_ping, "orders": load_open_orders()})
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("daemon boom")
        while should_continue():
            await sleep_fn(0)
            break


class RuntimeDaemonTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_invokes_supervisor(self):
        supervisor = FakeSupervisor()
        daemon = RuntimeDaemon(
            supervisor=supervisor,
            load_open_orders=lambda: [{"symbol": "BTC-USDT-SWAP", "order_id": "1"}],
        )

        await daemon.run_once(send_ping=True)

        self.assertEqual(supervisor.calls[0]["send_ping"], True)
        self.assertEqual(supervisor.calls[0]["orders"], [{"symbol": "BTC-USDT-SWAP", "order_id": "1"}])

    async def test_run_once_calls_single_iteration(self):
        class IterationSupervisor:
            def __init__(self):
                self.run_iteration_calls = []
                self.run_forever_called = False

            async def run_iteration(self, load_open_orders, send_ping=False):
                self.run_iteration_calls.append({"send_ping": send_ping, "orders": load_open_orders()})

            async def run_forever(self, load_open_orders, should_continue, sleep_fn, send_ping=False):
                self.run_forever_called = True
                raise AssertionError("run_forever should not be used by run_once")

        supervisor = IterationSupervisor()
        daemon = RuntimeDaemon(supervisor=supervisor, load_open_orders=lambda: [])

        await daemon.run_once(send_ping=False)

        self.assertEqual(len(supervisor.run_iteration_calls), 1)
        self.assertFalse(supervisor.run_forever_called)

    async def test_run_once_records_error(self):
        supervisor = FakeSupervisor()
        supervisor.fail_once = True
        daemon = RuntimeDaemon(supervisor=supervisor, load_open_orders=lambda: [])

        await daemon.run_once(send_ping=False)

        self.assertEqual(daemon.last_error, "daemon boom")

    async def test_stop_flips_running_flag(self):
        supervisor = FakeSupervisor()
        daemon = RuntimeDaemon(supervisor=supervisor, load_open_orders=lambda: [])
        daemon.running = True
        daemon.stop()
        self.assertFalse(daemon.running)


if __name__ == "__main__":
    unittest.main()
