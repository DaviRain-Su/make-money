from typing import Any, Dict, List, Optional, Sequence

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
        if last <= 0 or sod <= 0 or volume < min_volume_24h:
            continue
        change_pct = ((last - sod) / sod) * 100.0
        if change_pct < min_change_pct:
            continue
        candidates.append(
            {
                "instId": inst_id,
                "change_pct_24h": round(change_pct, 4),
                "volume_24h_quote": volume,
                "last": last,
            }
        )

    candidates.sort(key=lambda row: (row["change_pct_24h"], row["volume_24h_quote"]), reverse=True)
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
    return {
        "status": "ok",
        "count": len(results),
        "symbols": [row["instId"] for row in results],
        "results": results,
    }



def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
