from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent_trader.models import StrategySignal


@dataclass(frozen=True)
class Candle:
    ts: int              # 毫秒时间戳
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def parse_okx_candles(response: Dict[str, Any], include_unconfirmed: bool = False) -> List[Candle]:
    """Parse OKX candlesticks response into oldest-first Candle list.

    OKX returns rows as [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm],
    newest-first. We reverse and by default drop any still-forming bar so the
    strategy only acts on closed candles.
    """
    rows = response.get("data", []) if isinstance(response, dict) else []
    candles: List[Candle] = []
    for row in rows:
        if len(row) < 5:
            continue
        confirm = row[8] if len(row) > 8 else "1"
        if not include_unconfirmed and str(confirm) != "1":
            continue
        try:
            candles.append(
                Candle(
                    ts=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]) if len(row) > 5 and row[5] not in (None, "") else 0.0,
                )
            )
        except (TypeError, ValueError):
            continue
    candles.sort(key=lambda c: c.ts)
    return candles


@dataclass(frozen=True)
class EmaAtrConfig:
    fast_ema: int = 20
    slow_ema: int = 50
    atr_period: int = 14
    atr_stop_mult: float = 2.0
    atr_tp_mult: float = 3.0
    leverage: float = 2.0
    confidence: float = 0.6
    expected_slippage_bps: float = 8.0
    rationale: str = "ema_atr"



def compute_ema(values: List[float], period: int) -> List[Optional[float]]:
    if period <= 0:
        raise ValueError("period must be positive")
    result: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return result
    alpha = 2.0 / (period + 1)
    # seed with simple moving average of the first `period` values
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed
    for idx in range(period, len(values)):
        prev = values[idx] * alpha + prev * (1 - alpha)
        result[idx] = prev
    return result



def compute_atr(candles: List[Candle], period: int) -> List[Optional[float]]:
    if period <= 0:
        raise ValueError("period must be positive")
    result: List[Optional[float]] = [None] * len(candles)
    if len(candles) <= period:
        return result
    # True range for every bar after the first
    true_ranges: List[float] = [0.0]
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        high = candles[i].high
        low = candles[i].low
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    # Wilder's smoothing: seed ATR with SMA of first `period` true ranges,
    # starting at index `period`.
    seed = sum(true_ranges[1:period + 1]) / period
    result[period] = seed
    prev = seed
    for idx in range(period + 1, len(candles)):
        prev = (prev * (period - 1) + true_ranges[idx]) / period
        result[idx] = prev
    return result



def generate_ema_atr_signal(
    symbol: str,
    candles: List[Candle],
    config: EmaAtrConfig,
) -> Optional[StrategySignal]:
    """Inspects the most recent closed candle and returns a StrategySignal if
    a fast/slow EMA crossover just occurred. Candles must be oldest-first and
    contain only closed bars (caller drops any in-progress candle)."""
    if len(candles) <= max(config.slow_ema, config.atr_period) + 1:
        return None

    closes = [c.close for c in candles]
    fast = compute_ema(closes, config.fast_ema)
    slow = compute_ema(closes, config.slow_ema)
    atr = compute_atr(candles, config.atr_period)

    last = len(candles) - 1
    prev = last - 1
    fast_last, fast_prev = fast[last], fast[prev]
    slow_last, slow_prev = slow[last], slow[prev]
    atr_last = atr[last]
    if None in (fast_last, fast_prev, slow_last, slow_prev, atr_last):
        return None
    if atr_last <= 0:
        return None

    crossed_up = fast_prev <= slow_prev and fast_last > slow_last
    crossed_down = fast_prev >= slow_prev and fast_last < slow_last
    if not (crossed_up or crossed_down):
        return None

    entry = candles[last].close
    side = "buy" if crossed_up else "sell"
    if side == "buy":
        stop_loss = entry - config.atr_stop_mult * atr_last
        take_profit = entry + config.atr_tp_mult * atr_last
    else:
        stop_loss = entry + config.atr_stop_mult * atr_last
        take_profit = entry - config.atr_tp_mult * atr_last

    if stop_loss <= 0 or take_profit <= 0:
        return None

    return StrategySignal(
        side=side,
        confidence=config.confidence,
        entry_price=entry,
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        expected_slippage_bps=config.expected_slippage_bps,
        leverage=config.leverage,
        rationale=f"{config.rationale}:{config.fast_ema}/{config.slow_ema}",
        symbol=symbol,
    )
