"""Fire-and-forget alert channel, now with level-aware routing.

A single `ALERT_WEBHOOK_URL` (legacy) still works — every level falls
through to it when nothing more specific matches. For finer routing,
set one or more of:
  - ALERT_WEBHOOK_DANGER_URL  — paging-worthy events (risk block, halt)
  - ALERT_WEBHOOK_WARN_URL    — degraded but survivable (funding guard miss,
                                reconnect storm, reconcile mismatch)
  - ALERT_WEBHOOK_INFO_URL    — nice-to-know (strategy poll heartbeat, etc.)

Each URL gets its own POST with `{event_type, level, ...payload}`. Missing
URLs are simply skipped — the audit log remains the source of truth.

Backwards compatibility:
- If `alert_webhook_url` is set but no level-specific URL is provided, the
  generic channel receives all levels (current behaviour).
- `push_alert(webhook_url=..., ...)` still works unchanged.
- `push_level_alert(settings, level, ...)` is the new helper that consults
  level-specific routing.
"""

import json
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib import request as urllib_request


TransportFn = Callable[[str, Dict[str, str], Dict[str, Any], float], None]


DEFAULT_TIMEOUT_SECONDS = 5.0

ALERT_LEVELS = ("info", "warn", "danger")



def default_transport(url: str, headers: Dict[str, str], body: Dict[str, Any], timeout: float) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib_request.Request(url=url, data=data, headers=headers, method="POST")
    with urllib_request.urlopen(req, timeout=timeout) as response:
        response.read()



def push_alert(
    webhook_url: str,
    event_type: str,
    level: str,
    payload: Dict[str, Any],
    transport: Optional[TransportFn] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Deliver a single alert. Returns a result dict; never raises."""
    if not webhook_url:
        return {"status": "skipped", "reason": "no webhook url"}
    body = {
        "event_type": event_type,
        "level": level,
        **payload,
    }
    active = transport or default_transport
    try:
        active(webhook_url, {"Content-Type": "application/json"}, body, timeout)
        return {"status": "ok", "event_type": event_type, "level": level}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "event_type": event_type, "level": level, "error": f"{type(exc).__name__}: {exc}"}



def resolve_alert_urls(settings: Any, level: str) -> List[str]:
    """Return the ordered list of webhook URLs that should receive an alert
    of the given level. Caller loops over and fires each."""
    level = (level or "").lower()
    urls: List[str] = []
    level_specific = getattr(settings, f"alert_webhook_{level}_url", "") or ""
    if level_specific:
        urls.append(level_specific)
    generic = getattr(settings, "alert_webhook_url", "") or ""
    if generic and generic not in urls:
        urls.append(generic)
    return urls



def push_level_alert(
    settings: Any,
    event_type: str,
    level: str,
    payload: Dict[str, Any],
    transport: Optional[TransportFn] = None,
) -> List[Dict[str, Any]]:
    """Dispatch to every URL that routes the given level. Returns one result
    dict per URL attempted. If no URL is configured the list is empty."""
    urls = resolve_alert_urls(settings, level)
    if not urls:
        return []
    timeout = float(getattr(settings, "alert_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    results = []
    for url in urls:
        results.append(push_alert(url, event_type, level, payload, transport=transport, timeout=timeout))
    return results



def classify_signal_result(result: Dict[str, Any]) -> Optional[str]:
    """Map a pipeline result to an alert level.

    - execution blocked / risk rejected → danger
    - execution submitted / paper (approved)  → None (no alert)
    - execution disabled → info (system is deliberately off; not a fault)
    """
    risk = result.get("risk") or {}
    execution = result.get("execution") or {}
    status = execution.get("status")
    if status == "blocked" or risk.get("approved") is False:
        return "danger"
    if status == "disabled":
        return "info"
    return None
