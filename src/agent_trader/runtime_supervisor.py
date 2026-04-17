from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class RuntimeSupervisor:
    ws_manager: Any
    reconcile_scheduler: Any
    timestamp_fn: Callable[[], str]
    websocket_factory: Optional[Callable[[], Any]] = None
    iterations_run: int = 0

    async def run_iteration(self, load_open_orders: Callable[[], list], send_ping: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        timestamp = self.timestamp_fn()
        try:
            result["ws"] = await self.ws_manager.run_once(timestamp=timestamp, send_ping=send_ping)
        except Exception as exc:  # noqa: BLE001
            result["ws_error"] = str(exc)
            if self.websocket_factory is not None:
                await self.ws_manager.reconnect_async(self.websocket_factory(), timestamp=timestamp)
        open_orders = load_open_orders()
        if open_orders:
            result["scheduler"] = await self.reconcile_scheduler.run_cycle(open_orders)
        self.iterations_run += 1
        return result

    async def run_forever(
        self,
        load_open_orders: Callable[[], list],
        should_continue: Callable[[], bool],
        sleep_fn,
        send_ping: bool = False,
    ) -> None:
        while should_continue():
            await self.run_iteration(load_open_orders=load_open_orders, send_ping=send_ping)
            await sleep_fn(0)
