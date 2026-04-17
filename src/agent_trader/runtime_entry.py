from typing import Any, Callable

from agent_trader.main import build_strategy_scheduler, make_okx_ws_client, reconcile_open_orders_payload
from agent_trader.okx_ws import OKXWebSocketManager
from agent_trader.okx_ws_transport import AsyncWebSocketTransport, connect_with_websockets
from agent_trader.reconcile_scheduler import ReconcileScheduler
from agent_trader.runtime_daemon import RuntimeDaemon
from agent_trader.runtime_supervisor import RuntimeSupervisor



def build_runtime_daemon(current_settings, load_open_orders: Callable[[], list]):
    ws_client = make_okx_ws_client(current_settings)
    transport = AsyncWebSocketTransport(url=ws_client.url, connect_fn=connect_with_websockets)
    manager = OKXWebSocketManager(client=ws_client, inst_type="SWAP", inst_family="BTC-USDT")
    scheduler = ReconcileScheduler(
        runner=lambda open_orders: reconcile_open_orders_payload(open_orders, current_settings=current_settings),
        poll_interval_seconds=current_settings.reconcile_poll_interval_seconds,
    )
    supervisor = RuntimeSupervisor(
        ws_manager=manager,
        reconcile_scheduler=scheduler,
        timestamp_fn=lambda: "0",
        websocket_factory=lambda: transport,
    )
    strategy_scheduler = None
    if getattr(current_settings, "strategy_enabled", False):
        strategy_scheduler = build_strategy_scheduler(current_settings)
    daemon = RuntimeDaemon(
        supervisor=supervisor,
        load_open_orders=load_open_orders,
        strategy_scheduler=strategy_scheduler,
    )
    return daemon
