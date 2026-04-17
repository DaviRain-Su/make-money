import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

from agent_trader.audit_log import append_audit_event
from agent_trader.config import Settings
from agent_trader.control_state import halt_trading, read_control_state, resume_trading
from agent_trader.models import StrategySignal


CLOCK_SKEW_SECONDS = 60
LARGE_TIER = "large"
MEDIUM_TIER = "medium"
SMALL_TIER = "small"


class AdminAuthError(PermissionError):
    pass


class AdminReplayError(ValueError):
    pass


class AdminTierViolation(ValueError):
    pass


def _canonical_body(body: Optional[Dict[str, Any]]) -> str:
    if body is None:
        return ""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hmac(secret: str, timestamp: str, nonce: str, path: str, body: Optional[Dict[str, Any]]) -> str:
    message = f"{timestamp}.{nonce}.{path}.{_canonical_body(body)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _verify_hmac(
    settings: Settings,
    path: str,
    timestamp: str,
    nonce: str,
    signature: str,
    body: Optional[Dict[str, Any]],
    now: Optional[float] = None,
) -> None:
    if not settings.admin_shared_secret:
        raise AdminAuthError("admin secret not configured")
    if not timestamp or not nonce or not signature:
        raise AdminAuthError("missing auth fields")
    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        raise AdminAuthError("invalid timestamp") from exc
    current = int(now if now is not None else time.time())
    if abs(current - ts_int) > CLOCK_SKEW_SECONDS:
        raise AdminAuthError("timestamp outside clock skew window")
    expected = compute_hmac(settings.admin_shared_secret, timestamp, nonce, path, body)
    if not hmac.compare_digest(expected, signature):
        raise AdminAuthError("invalid signature")


def _consume_nonce(settings: Settings, nonce: str) -> None:
    path = settings.admin_nonce_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    seen = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                value = line.strip()
                if value:
                    seen.add(value)
    if nonce in seen:
        raise AdminReplayError("nonce already used")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(nonce + "\n")


def _authorize(
    settings: Settings,
    path: str,
    timestamp: str,
    nonce: str,
    signature: str,
    body: Optional[Dict[str, Any]],
    now: Optional[float] = None,
) -> None:
    _verify_hmac(settings, path, timestamp, nonce, signature, body, now=now)
    _consume_nonce(settings, nonce)


def _log_admin_event(settings: Settings, event: Dict[str, Any]) -> None:
    append_audit_event(
        settings.audit_log_path,
        {"event_type": "admin_action", **event},
    )


def classify_trade_tier(notional_usd: float, settings: Settings) -> str:
    if notional_usd >= settings.admin_large_trade_usd:
        return LARGE_TIER
    if notional_usd >= settings.admin_small_trade_usd:
        return MEDIUM_TIER
    return SMALL_TIER


def handle_status(
    settings: Settings,
    timestamp: str,
    nonce: str,
    signature: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    _authorize(settings, "/admin/status", timestamp, nonce, signature, body=None, now=now)
    state = read_control_state(settings.control_state_path)
    return {
        "environment": settings.environment,
        "execution_enabled": settings.execution_enabled,
        "paper_mode": settings.paper_mode,
        "trading_halted": state.trading_halted,
        "halt_reason": state.halt_reason,
        "halted_at": state.halted_at,
        "halted_by": state.halted_by,
    }


def handle_halt(
    settings: Settings,
    body: Dict[str, Any],
    timestamp: str,
    nonce: str,
    signature: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    _authorize(settings, "/admin/halt", timestamp, nonce, signature, body=body, now=now)
    reason = str(body.get("reason", "unspecified"))
    actor = str(body.get("actor", "hermes"))
    state = halt_trading(settings.control_state_path, reason=reason, actor=actor)
    _log_admin_event(
        settings,
        {
            "action": "halt",
            "reason": reason,
            "actor": actor,
            "trading_halted": state.trading_halted,
        },
    )
    return {"trading_halted": state.trading_halted, "halt_reason": state.halt_reason, "halted_by": state.halted_by}


def handle_resume(
    settings: Settings,
    body: Dict[str, Any],
    timestamp: str,
    nonce: str,
    signature: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    _authorize(settings, "/admin/resume", timestamp, nonce, signature, body=body, now=now)
    actor = str(body.get("actor", "hermes"))
    resume_trading(settings.control_state_path)
    _log_admin_event(settings, {"action": "resume", "actor": actor, "trading_halted": False})
    return {"trading_halted": False}


def handle_manual_trade(
    settings: Settings,
    body: Dict[str, Any],
    timestamp: str,
    nonce: str,
    signature: str,
    pipeline_runner,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    _authorize(settings, "/admin/manual_trade", timestamp, nonce, signature, body=body, now=now)
    notional_usd = float(body.get("notional_usd", 0.0))
    tier = classify_trade_tier(notional_usd, settings)
    confirmation = str(body.get("confirmation", "")).lower()
    pin = str(body.get("pin", ""))
    if tier == LARGE_TIER:
        if confirmation != "confirmed" or pin != settings.admin_shared_secret:
            raise AdminTierViolation("large trade requires confirmation and pin")
    elif tier == MEDIUM_TIER:
        if confirmation != "confirmed":
            raise AdminTierViolation("medium trade requires confirmation")
    reference_price = float(body.get("reference_price") or body.get("entry_price"))
    stop_distance = float(body.get("stop_distance_usd", 0.0))
    if stop_distance <= 0:
        stop_loss_price = float(body.get("stop_loss_price", 0.0))
        if stop_loss_price <= 0:
            raise AdminTierViolation("stop_loss_price or stop_distance_usd required")
    else:
        stop_loss_price = reference_price - stop_distance if body.get("side", "buy").lower() == "buy" else reference_price + stop_distance
    take_profit_price = float(body.get("take_profit_price", reference_price))
    signal = StrategySignal(
        side=str(body.get("side", "buy")),
        confidence=float(body.get("confidence", 1.0)),
        entry_price=reference_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        expected_slippage_bps=float(body.get("expected_slippage_bps", 5.0)),
        leverage=float(body.get("leverage", 1.0)),
        rationale=str(body.get("rationale", "hermes-manual")),
        position_action=str(body.get("position_action", "OPEN")).upper(),
        pos_side=str(body.get("pos_side", "")),
        symbol=(body.get("symbol") or None),
    )
    result = pipeline_runner(signal=signal, current_settings=settings)
    _log_admin_event(
        settings,
        {
            "action": "manual_trade",
            "tier": tier,
            "actor": str(body.get("actor", "hermes")),
            "notional_usd": notional_usd,
            "risk_approved": result.get("risk", {}).get("approved"),
            "execution_status": result.get("execution", {}).get("status"),
            "order_id": result.get("execution", {}).get("order_id"),
        },
    )
    return {
        "tier": tier,
        "signal": asdict(signal),
        "risk": result.get("risk"),
        "execution": result.get("execution"),
    }
