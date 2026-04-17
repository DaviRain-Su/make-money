from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class RuntimeDaemon:
    supervisor: Any
    load_open_orders: Callable[[], list]
    running: bool = False
    last_error: Optional[str] = None

    async def run_once(self, send_ping: bool = False) -> None:
        self.running = True
        try:
            await self.supervisor.run_forever(
                load_open_orders=self.load_open_orders,
                should_continue=lambda: self.running,
                sleep_fn=lambda _: _noop_sleep(),
                send_ping=send_ping,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
        finally:
            self.running = False

    def stop(self) -> None:
        self.running = False


async def _noop_sleep() -> None:
    return None
