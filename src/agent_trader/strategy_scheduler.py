"""Periodic strategy poll loop.

Mirrors ReconcileScheduler in shape: an async loop that invokes a user-
supplied runner every `poll_interval_seconds`. The runner is wired to
`run_strategy_poll` in production. Stays off by default — the caller decides
whether to schedule it at all.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional



@dataclass
class StrategyScheduler:
    runner: Callable[[], Dict[str, Any]]
    poll_interval_seconds: int
    last_result: Optional[Dict[str, Any]] = None
    cycles_run: int = 0

    async def run_cycle(self) -> Dict[str, Any]:
        self.last_result = self.runner()
        self.cycles_run += 1
        return self.last_result

    async def run_forever(
        self,
        should_continue: Callable[[], bool],
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        while should_continue():
            try:
                await self.run_cycle()
            except Exception:  # noqa: BLE001
                # Never let a single poll failure kill the loop. Errors are
                # surfaced inside the runner's return payload anyway.
                pass
            await sleep_fn(self.poll_interval_seconds)
