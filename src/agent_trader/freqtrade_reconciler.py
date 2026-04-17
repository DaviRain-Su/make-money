"""Reverse adapter: when our risk engine rejects (or materially diverges
from) a trade that freqtrade thinks it opened, call back into freqtrade's
REST API so its internal trade database matches reality.

Freqtrade exposes a `POST /api/v1/forceexit` endpoint that closes an open
trade by id. We use that to reconcile: if agent_trader blocked the trade,
freqtrade should drop the phantom position from its books.

Design notes:
- Fire-and-forget from the caller's perspective; a failure to reconcile does
  not block order processing (we can't undo the risk-engine decision anyway).
- Networking is injected so tests can exercise every branch without hitting
  a real freqtrade instance.
"""

import base64
import json
from typing import Any, Callable, Dict, Optional
from urllib import request as urllib_request


TransportFn = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]]], Dict[str, Any]]



def default_transport(method: str, url: str, headers: Dict[str, str], json_body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = None if json_body is None else json.dumps(json_body).encode("utf-8")
    req = urllib_request.Request(url=url, data=data, headers=headers, method=method)
    with urllib_request.urlopen(req, timeout=10) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}



def force_exit_trade(
    api_url: str,
    username: str,
    password: str,
    trade_id: Any,
    transport: Optional[TransportFn] = None,
) -> Dict[str, Any]:
    if not api_url:
        raise ValueError("freqtrade api url is not configured")
    if trade_id in (None, ""):
        raise ValueError("trade_id required")
    endpoint = f"{api_url.rstrip('/')}/api/v1/forceexit"
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    active_transport = transport or default_transport
    return active_transport("POST", endpoint, headers, {"tradeid": trade_id})
