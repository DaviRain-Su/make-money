"""OKX perpetual funding rate helpers.

OKX exposes `/public/funding-rate` with the current funding rate for a SWAP
instrument. Large-magnitude funding means one side is paying the other a lot
to hold positions — entering on the paying side is a structural headwind.

This module fetches the rate, caches briefly, and exposes a `FundingGuard`
that tells the risk pipeline whether a given symbol's funding rate is
within an acceptable band.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional



@dataclass
class FundingSnapshot:
    symbol: str
    funding_rate: float      # Decimal, e.g. 0.0001 = 0.01% per funding period
    next_funding_time_ms: int
    fetched_at_ms: int



def parse_funding_rate_response(response: Dict[str, Any]) -> Optional[FundingSnapshot]:
    """Parse OKX /public/funding-rate payload into a FundingSnapshot. Returns
    None when the payload is missing or malformed."""
    rows = response.get("data", []) if isinstance(response, dict) else []
    if not rows:
        return None
    row = rows[0]
    try:
        rate = float(row.get("fundingRate"))
    except (TypeError, ValueError):
        return None
    symbol = row.get("instId", "")
    next_ts = row.get("nextFundingTime") or row.get("fundingTime") or "0"
    try:
        next_ts_int = int(next_ts)
    except (TypeError, ValueError):
        next_ts_int = 0
    return FundingSnapshot(
        symbol=symbol,
        funding_rate=rate,
        next_funding_time_ms=next_ts_int,
        fetched_at_ms=int(time.time() * 1000),
    )



def fetch_funding_rate(client: Any, inst_id: str) -> Optional[FundingSnapshot]:
    """Call `client.get_funding_rate(inst_id)` and return a snapshot."""
    try:
        response = client.get_funding_rate(inst_id)
    except Exception:  # noqa: BLE001
        return None
    snap = parse_funding_rate_response(response if isinstance(response, dict) else {})
    if snap is None:
        return None
    # if the payload dropped symbol, inherit the requested one
    if not snap.symbol:
        return FundingSnapshot(
            symbol=inst_id,
            funding_rate=snap.funding_rate,
            next_funding_time_ms=snap.next_funding_time_ms,
            fetched_at_ms=snap.fetched_at_ms,
        )
    return snap



@dataclass
class FundingGuard:
    """Caches funding rates for `ttl_seconds` and says whether an entry on
    `side` for `symbol` exceeds `max_abs_bps`. Rate is in decimal; we
    convert to bps by *10_000.
    """
    client: Any
    max_abs_bps: float = 0.0
    ttl_seconds: int = 300
    cache: Dict[str, FundingSnapshot] = field(default_factory=dict)

    def is_enabled(self) -> bool:
        return self.max_abs_bps > 0

    def _fresh_snapshot(self, symbol: str) -> Optional[FundingSnapshot]:
        cached = self.cache.get(symbol)
        now_ms = int(time.time() * 1000)
        if cached is not None and now_ms - cached.fetched_at_ms < self.ttl_seconds * 1000:
            return cached
        snap = fetch_funding_rate(self.client, symbol)
        if snap is not None:
            self.cache[symbol] = snap
        return snap

    def check(self, symbol: str, side: str) -> Dict[str, Any]:
        """Return {allowed, reason, funding_rate, funding_bps}.

        Blocks when entering a long while funding is strongly positive
        (longs pay shorts) or a short while funding is strongly negative
        (shorts pay longs). The magnitude gate applies in either direction
        when |rate| exceeds the threshold; direction signal refines it.
        """
        if not self.is_enabled():
            return {"allowed": True, "reason": "disabled"}
        snap = self._fresh_snapshot(symbol)
        if snap is None:
            # fail-open: if we can't read the rate, don't block new trades
            return {"allowed": True, "reason": "snapshot_unavailable"}
        rate_bps = snap.funding_rate * 10_000.0
        abs_bps = abs(rate_bps)
        payload = {
            "funding_rate": snap.funding_rate,
            "funding_bps": rate_bps,
            "threshold_bps": self.max_abs_bps,
            "next_funding_time_ms": snap.next_funding_time_ms,
        }
        if abs_bps <= self.max_abs_bps:
            return {"allowed": True, "reason": "within_threshold", **payload}
        ss = (side or "").lower()
        if ss == "buy" and rate_bps > 0:
            return {"allowed": False, "reason": "funding_cost_long", **payload}
        if ss == "sell" and rate_bps < 0:
            return {"allowed": False, "reason": "funding_cost_short", **payload}
        # beyond threshold but in our favor: still allow (we're the receiver)
        return {"allowed": True, "reason": "beyond_threshold_in_favor", **payload}
