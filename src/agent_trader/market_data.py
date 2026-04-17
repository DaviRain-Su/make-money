"""Historical candle loader for OKX SWAP instruments.

OKX returns candlesticks newest-first, ~100 per page, and exposes a
`history-candlesticks` endpoint that can go back further. This module pages
backward until it has the desired number of bars (or runs out of history),
persists the result to a JSONL cache under `var/cache/market_data/`, and
reuses that cache on the next call so backtests don't re-hit the API.

Kept deliberately simple:
- Forward/reverse incremental refresh is left for later; for now
  `load_or_fetch_candles` either returns cached data (if the cache already
  holds at least `min_count` confirmed bars) or fetches fresh.
- Transport is implicit (client.get_candles / client.get_history_candles);
  tests inject fakes.
"""

import json
import os
from dataclasses import asdict
from typing import Any, Callable, Iterable, List, Optional

from agent_trader.strategy import Candle, parse_okx_candles


CandleFetcher = Callable[[str, str, str, str], Any]  # inst_id, bar, after, limit



def fetch_historical_candles(
    client: Any,
    inst_id: str,
    bar: str = "1H",
    target_count: int = 500,
    page_limit: int = 100,
    max_pages: int = 50,
) -> List[Candle]:
    """Pulls `target_count` closed candles by walking backward through OKX.

    Uses `client.get_candles(inst_id, bar, limit)` for the most recent page
    (if available) and `client.get_history_candles(inst_id, bar, after, limit)`
    for older pages. `after` is the earliest ts we've seen so far, in ms.
    """
    if target_count <= 0:
        return []

    accumulated: List[Candle] = []
    seen_ts = set()

    # First page: latest candles via regular market endpoint.
    try:
        latest_resp = client.get_candles(inst_id, bar=bar, limit=str(page_limit))
    except AttributeError:
        latest_resp = None
    if latest_resp is not None:
        page = parse_okx_candles(latest_resp)
        for c in page:
            if c.ts not in seen_ts:
                accumulated.append(c)
                seen_ts.add(c.ts)

    pages_fetched = 0
    while len(accumulated) < target_count and pages_fetched < max_pages:
        earliest = min((c.ts for c in accumulated), default=None)
        if earliest is None:
            break
        try:
            older_resp = client.get_history_candles(
                inst_id, bar=bar, after=str(earliest), limit=str(page_limit)
            )
        except AttributeError:
            break
        page = parse_okx_candles(older_resp)
        new_page = [c for c in page if c.ts not in seen_ts]
        if not new_page:
            break
        for c in new_page:
            accumulated.append(c)
            seen_ts.add(c.ts)
        pages_fetched += 1

    accumulated.sort(key=lambda c: c.ts)
    if len(accumulated) > target_count:
        accumulated = accumulated[-target_count:]
    return accumulated



def cache_path_for(cache_dir: str, inst_id: str, bar: str) -> str:
    safe = f"{inst_id.replace('/', '_')}_{bar}.jsonl"
    return os.path.join(cache_dir, safe)



def save_candles_to_cache(path: str, candles: Iterable[Candle]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for c in candles:
            handle.write(json.dumps(asdict(c)) + "\n")



def load_candles_from_cache(path: str) -> List[Candle]:
    if not os.path.exists(path):
        return []
    candles: List[Candle] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                candles.append(
                    Candle(
                        ts=int(row["ts"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                    )
                )
            except (ValueError, KeyError, TypeError):
                continue
    candles.sort(key=lambda c: c.ts)
    return candles



def load_or_fetch_candles(
    client: Any,
    inst_id: str,
    bar: str = "1H",
    target_count: int = 500,
    cache_dir: str = "var/cache/market_data",
    refresh: bool = False,
    page_limit: int = 100,
    max_pages: int = 50,
) -> List[Candle]:
    """Return up to `target_count` closed candles for (inst_id, bar), preferring
    on-disk cache. When the cache has ≥ target_count bars and `refresh=False`,
    no network call happens."""
    path = cache_path_for(cache_dir, inst_id, bar)
    cached = load_candles_from_cache(path)
    if not refresh and len(cached) >= target_count:
        return cached[-target_count:]

    fetched = fetch_historical_candles(
        client=client,
        inst_id=inst_id,
        bar=bar,
        target_count=target_count,
        page_limit=page_limit,
        max_pages=max_pages,
    )
    # merge cached + fetched, dedup by ts
    merged: dict = {c.ts: c for c in cached}
    for c in fetched:
        merged[c.ts] = c
    final = sorted(merged.values(), key=lambda c: c.ts)
    save_candles_to_cache(path, final)
    if len(final) > target_count:
        return final[-target_count:]
    return final
