"""Fire-and-forget alert channel.

Pushes structured JSON payloads to `ALERT_WEBHOOK_URL` when "danger"-class
events happen (risk block, halt, critical errors). The webhook URL can be:
- a Telegram bot webhook
- Hermes' inbound endpoint
- any Slack / PagerDuty / custom relay

Kept deliberately simple:
- No retries. If alert delivery fails, the audit log still has the event.
- Short timeout so we don't block the request path.
- Transport is injectable for tests.
"""

import json
from typing import Any, Callable, Dict, Optional
from urllib import request as urllib_request


TransportFn = Callable[[str, Dict[str, str], Dict[str, Any], float], None]


DEFAULT_TIMEOUT_SECONDS = 5.0



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



def classify_signal_result(result: Dict[str, Any]) -> Optional[str]:
    """Return an alert level for a pipeline result, or None if it's boring."""
    risk = result.get("risk") or {}
    execution = result.get("execution") or {}
    if execution.get("status") == "blocked" or risk.get("approved") is False:
        return "danger"
    return None
