import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ControlState:
    trading_halted: bool
    halt_reason: str
    halted_at: Optional[str]
    halted_by: Optional[str]


def _empty_state() -> ControlState:
    return ControlState(trading_halted=False, halt_reason="", halted_at=None, halted_by=None)


def read_control_state(path: str) -> ControlState:
    if not os.path.exists(path):
        return _empty_state()
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return _empty_state()
    data: Dict[str, Any] = json.loads(raw)
    return ControlState(
        trading_halted=bool(data.get("trading_halted", False)),
        halt_reason=str(data.get("halt_reason", "")),
        halted_at=data.get("halted_at"),
        halted_by=data.get("halted_by"),
    )


def write_control_state(path: str, state: ControlState) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "trading_halted": state.trading_halted,
        "halt_reason": state.halt_reason,
        "halted_at": state.halted_at,
        "halted_by": state.halted_by,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)


def halt_trading(path: str, reason: str, actor: str) -> ControlState:
    state = ControlState(
        trading_halted=True,
        halt_reason=reason,
        halted_at=datetime.now(timezone.utc).isoformat(),
        halted_by=actor,
    )
    write_control_state(path, state)
    return state


def resume_trading(path: str) -> ControlState:
    state = _empty_state()
    write_control_state(path, state)
    return state
