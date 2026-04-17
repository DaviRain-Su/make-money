import asyncio
import inspect
from typing import Any, Dict, Optional

from agent_trader.config import Settings, load_settings
from agent_trader.main import account_state_payload, okx_account_state_payload, reconcile_open_orders_payload
from agent_trader.runtime_entry import build_runtime_daemon


def _run_maybe_async(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def run_local_healthcheck(current_settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = current_settings or load_settings()
    account = okx_account_state_payload(current_settings=settings) if settings.use_okx_native else account_state_payload(current_settings=settings)
    reconciliation = reconcile_open_orders_payload([], current_settings=settings)
    daemon = build_runtime_daemon(current_settings=settings, load_open_orders=lambda: [])
    _run_maybe_async(daemon.run_once(send_ping=True))
    runtime_error = getattr(daemon, "last_error", None)
    runtime = {
        "status": "error" if runtime_error else "ok",
        "error": runtime_error,
    }
    return {
        "status": "degraded" if runtime_error else "ok",
        "settings": {
            "environment": settings.environment,
            "use_okx_native": settings.use_okx_native,
            "okx_symbol": settings.okx_symbol,
            "okx_flag": settings.okx_flag,
            "execution_enabled": settings.execution_enabled,
            "paper_mode": settings.paper_mode,
            "proposal_risk_fraction": settings.proposal_risk_fraction,
            "risk_min_equity_usd": settings.risk_limits.min_equity_usd,
            "risk_max_margin_utilization": settings.risk_limits.max_margin_utilization,
        },
        "account": account,
        "reconciliation": reconciliation,
        "runtime": runtime,
    }
