import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ReconcileScheduler:
    runner: Callable[[List[Dict[str, str]]], Dict[str, Any]]
    poll_interval_seconds: int
    last_result: Optional[Dict[str, Any]] = None
    cycles_run: int = 0

    async def run_cycle(self, open_orders: List[Dict[str, str]]) -> Dict[str, Any]:
        self.last_result = self.runner(open_orders)
        self.cycles_run += 1
        return self.last_result

    async def run_forever(
        self,
        load_open_orders: Callable[[], List[Dict[str, str]]],
        should_continue: Callable[[], bool],
        sleep_fn: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        while should_continue():
            open_orders = load_open_orders()
            if open_orders:
                await self.run_cycle(open_orders)
            await sleep_fn(self.poll_interval_seconds)
