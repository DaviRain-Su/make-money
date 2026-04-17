import json
import os
from collections import deque
from typing import Any, Dict, List


def read_recent_audit_events(path: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    recent: deque = deque(maxlen=max(limit, 1))
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                recent.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(recent)


def classify_event(event: Dict[str, Any]) -> str:
    event_type = event.get("event_type", "")
    if event_type == "admin_action":
        return "admin"
    if event_type == "risk_decision":
        return "danger" if event.get("risk_approved") is False else "ok"
    if event_type == "order_submitted":
        status = event.get("execution_status")
        if status == "blocked":
            return "danger"
        if status == "submitted":
            return "ok"
        return "info"
    if event_type == "order_reconciled":
        status = event.get("reconciliation_status")
        return "ok" if status == "filled" else "info"
    return "info"


def summarize_events(events: List[Dict[str, Any]]) -> Dict[str, int]:
    counters = {"risk_blocked": 0, "orders_submitted": 0, "orders_filled": 0, "admin_actions": 0}
    for event in events:
        event_type = event.get("event_type", "")
        if event_type == "risk_decision" and event.get("risk_approved") is False:
            counters["risk_blocked"] += 1
        elif event_type == "order_submitted" and event.get("execution_status") == "submitted":
            counters["orders_submitted"] += 1
        elif event_type == "order_reconciled" and event.get("reconciliation_status") == "filled":
            counters["orders_filled"] += 1
        elif event_type == "admin_action":
            counters["admin_actions"] += 1
    return counters
