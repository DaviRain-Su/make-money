import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class RuntimeDaemon:
    """Top-level runtime that orchestrates the ws+reconcile supervisor and,
    optionally, the periodic strategy scheduler. `run_once` mirrors the
    previous single-iteration shape used in tests. `run_forever` drives
    both subsystems concurrently until `should_continue()` returns False."""

    supervisor: Any
    load_open_orders: Callable[[], list]
    strategy_scheduler: Optional[Any] = None
    running: bool = False
    last_error: Optional[str] = None

    async def run_once(self, send_ping: bool = False) -> None:
        self.running = True
        self.last_error = None
        try:
            await self.supervisor.run_iteration(
                load_open_orders=self.load_open_orders,
                send_ping=send_ping,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
        finally:
            self.running = False

    async def run_forever(
        self,
        should_continue: Callable[[], bool],
        sleep_fn: Callable[[float], Any] = asyncio.sleep,
        send_ping: bool = False,
    ) -> None:
        self.running = True
        self.last_error = None
        tasks = []
        tasks.append(asyncio.ensure_future(self._supervisor_loop(should_continue, sleep_fn, send_ping)))
        if self.strategy_scheduler is not None:
            tasks.append(asyncio.ensure_future(self._strategy_loop(should_continue, sleep_fn)))
        try:
            await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
        finally:
            self.running = False

    async def _supervisor_loop(self, should_continue, sleep_fn, send_ping):
        while should_continue():
            try:
                await self.supervisor.run_iteration(
                    load_open_orders=self.load_open_orders,
                    send_ping=send_ping,
                )
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
            await sleep_fn(0)

    async def _strategy_loop(self, should_continue, sleep_fn):
        await self.strategy_scheduler.run_forever(
            should_continue=should_continue,
            sleep_fn=sleep_fn,
        )

    def stop(self) -> None:
        self.running = False


async def _noop_sleep() -> None:
    return None
