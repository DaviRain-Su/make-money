from typing import Any, Dict, List, Optional, Sequence
from collections import Counter

from agent_trader.config import Settings, load_settings
from agent_trader.okx_client import OKXClient, OKXCredentials


DEFAULT_EXCLUDE_SYMBOLS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
    "XRP-USDT-SWAP",
    "DOGE-USDT-SWAP",
)


def screen_okx_alt_swaps(
    client: Any,
    top_n: int = 10,
    quote: str = "USDT",
    min_change_pct: float = 1.0,
    min_volume_24h: float = 5_000_000.0,
    exclude_symbols: Sequence[str] = (),
) -> List[Dict[str, float]]:
    instruments_response = client.get_instruments("SWAP")
    tickers_response = client.get_tickers("SWAP")

    suffix = f"-{quote}-SWAP"
    excluded = {symbol for symbol in DEFAULT_EXCLUDE_SYMBOLS}
    excluded.update(symbol for symbol in exclude_symbols if symbol)

    tradable = {
        row.get("instId"): row
        for row in (instruments_response.get("data", []) if isinstance(instruments_response, dict) else [])
        if row.get("instId", "").endswith(suffix) and row.get("state", "live") == "live"
    }

    candidates: List[Dict[str, float]] = []
    for ticker in tickers_response.get("data", []) if isinstance(tickers_response, dict) else []:
        inst_id = ticker.get("instId", "")
        if inst_id not in tradable or inst_id in excluded:
            continue
        last = _safe_float(ticker.get("last"))
        sod = _safe_float(ticker.get("sodUtc0"))
        volume = _safe_float(ticker.get("volCcy24h"))
        high_24h = _safe_float(ticker.get("high24h"))
        low_24h = _safe_float(ticker.get("low24h"))
        ask = _safe_float(ticker.get("askPx"))
        bid = _safe_float(ticker.get("bidPx"))
        if last <= 0 or sod <= 0 or volume < min_volume_24h:
            continue
        change_pct = ((last - sod) / sod) * 100.0
        if change_pct < min_change_pct:
            continue
        distance_from_high_pct = ((high_24h - last) / high_24h) * 100.0 if high_24h > 0 else 999.0
        spread_bps = ((ask - bid) / last) * 10_000.0 if ask > 0 and bid > 0 and last > 0 else 0.0
        range_pct = ((high_24h - low_24h) / low_24h) * 100.0 if high_24h > 0 and low_24h > 0 else 0.0
        category = _categorize_candidate(change_pct, distance_from_high_pct)
        risk_flags = _risk_flags(change_pct, spread_bps, volume, min_volume_24h)
        if "high_spread" in risk_flags:
            category = "watchlist"
        score = _score_candidate(
            change_pct=change_pct,
            volume_24h=volume,
            min_volume_24h=min_volume_24h,
            distance_from_high_pct=distance_from_high_pct,
            spread_bps=spread_bps,
            category=category,
        )
        candidates.append(
            {
                "instId": inst_id,
                "category": category,
                "score": round(score, 2),
                "change_pct_24h": round(change_pct, 4),
                "volume_24h_quote": volume,
                "last": last,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "distance_from_high_pct": round(distance_from_high_pct, 4),
                "spread_bps": round(spread_bps, 4),
                "range_pct_24h": round(range_pct, 4),
                "risk_flags": risk_flags,
            }
        )

    candidates.sort(key=lambda row: (row["score"], row["change_pct_24h"], row["volume_24h_quote"]), reverse=True)
    if top_n <= 0:
        return candidates
    return candidates[:top_n]


def run_alt_screener(current_settings: Optional[Settings] = None, client: Optional[OKXClient] = None) -> Dict[str, Any]:
    settings = current_settings or load_settings()
    active_client = client or OKXClient.from_credentials(
        OKXCredentials(
            api_key=settings.okx_api_key,
            api_secret=settings.okx_api_secret,
            passphrase=settings.okx_passphrase,
            flag=settings.okx_flag,
        ),
        td_mode=settings.okx_td_mode,
    )
    results = screen_okx_alt_swaps(
        client=active_client,
        top_n=settings.strategy_alt_top_n,
        min_change_pct=settings.strategy_alt_min_change_pct,
        min_volume_24h=settings.strategy_alt_min_volume_24h,
        exclude_symbols=settings.strategy_alt_exclude_symbols,
    )
    category_counts = Counter(row["category"] for row in results)
    return {
        "status": "ok",
        "count": len(results),
        "symbols": [row["instId"] for row in results],
        "summary": {
            "category_counts": dict(category_counts),
            "top_score": results[0]["score"] if results else 0.0,
            "filters": {
                "top_n": settings.strategy_alt_top_n,
                "min_change_pct": settings.strategy_alt_min_change_pct,
                "min_volume_24h": settings.strategy_alt_min_volume_24h,
            },
        },
        "results": results,
    }



def _categorize_candidate(change_pct: float, distance_from_high_pct: float) -> str:
    if change_pct >= 5.0 and distance_from_high_pct <= 2.0:
        return "breakout"
    if change_pct >= 3.0 and distance_from_high_pct <= 8.0:
        return "pullback_watch"
    return "watchlist"



def _risk_flags(change_pct: float, spread_bps: float, volume_24h: float, min_volume_24h: float) -> List[str]:
    flags: List[str] = []
    if spread_bps >= 150.0:
        flags.append("high_spread")
    if change_pct >= 25.0:
        flags.append("parabolic")
    if volume_24h <= min_volume_24h * 1.5:
        flags.append("thin_relative_volume")
    return flags



def _score_candidate(
    change_pct: float,
    volume_24h: float,
    min_volume_24h: float,
    distance_from_high_pct: float,
    spread_bps: float,
    category: str,
) -> float:
    change_component = min(change_pct, 25.0) / 25.0 * 45.0
    volume_component = min(volume_24h / max(min_volume_24h, 1.0), 5.0) / 5.0 * 30.0
    proximity_component = max(0.0, 10.0 - min(distance_from_high_pct, 10.0)) / 10.0 * 15.0
    spread_penalty = min(spread_bps, 200.0) / 200.0 * 10.0
    category_bonus = 10.0 if category == "breakout" else 4.0 if category == "pullback_watch" else 0.0
    return max(0.0, change_component + volume_component + proximity_component + category_bonus - spread_penalty)



def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
