"""Grid search over EMA/ATR strategy parameters using our backtester.

Purpose: sweep a parameter grid, backtest each combination against the same
historical candles, score and rank. Because the backtester passes every
signal through `evaluate_trade`, the scoring naturally reflects "strategy +
risk engine" composite performance — the top rows are combos that both
make money AND survive the risk rules.
"""

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, Iterable, List, Optional

from agent_trader.backtest import BacktestReport, run_backtest
from agent_trader.models import RiskLimits
from agent_trader.strategy import Candle, EmaAtrConfig, generate_ema_atr_signal



@dataclass
class GridSearchRow:
    params: Dict[str, Any]
    report: BacktestReport

    @property
    def total_pnl_usd(self) -> float:
        return self.report.total_pnl_usd

    @property
    def win_rate(self) -> float:
        return self.report.win_rate

    @property
    def max_drawdown_pct(self) -> float:
        return self.report.max_drawdown_pct

    @property
    def signals_total(self) -> int:
        return self.report.signals_total

    @property
    def signals_approved(self) -> int:
        return self.report.signals_approved

    @property
    def block_rate(self) -> float:
        if self.report.signals_total == 0:
            return 0.0
        return self.report.signals_blocked / self.report.signals_total

    def summary(self) -> Dict[str, Any]:
        return {
            "params": self.params,
            "total_pnl_usd": round(self.total_pnl_usd, 2),
            "win_rate": round(self.win_rate, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "signals_total": self.signals_total,
            "signals_approved": self.signals_approved,
            "signals_blocked": self.report.signals_blocked,
            "block_rate": round(self.block_rate, 4),
            "trades": len(self.report.closed_trades),
            "top_block_reasons": _top_n_dict(self.report.block_reasons, 3),
        }



@dataclass
class GridSearchResult:
    rows: List[GridSearchRow] = field(default_factory=list)

    def ranked_by_score(self, drawdown_weight: float = 100.0, block_weight: float = 50.0) -> List[GridSearchRow]:
        """Higher score = better. Penalize drawdown and block rate."""
        def score(row: GridSearchRow) -> float:
            return (
                row.total_pnl_usd
                - drawdown_weight * row.max_drawdown_pct
                - block_weight * row.block_rate
            )
        return sorted(self.rows, key=score, reverse=True)

    def top_summaries(self, n: int = 10, **score_kwargs) -> List[Dict[str, Any]]:
        return [row.summary() for row in self.ranked_by_score(**score_kwargs)[:n]]



def grid_search_ema_atr(
    candles_by_symbol: Dict[str, List[Candle]],
    param_grid: Dict[str, Iterable[Any]],
    initial_equity_usd: float,
    risk_limits: RiskLimits,
    base_config: Optional[EmaAtrConfig] = None,
    allowed_symbols: Optional[Iterable[str]] = None,
    risk_fraction: float = 0.1,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    min_bars_for_signal: int = 30,
) -> GridSearchResult:
    """Iterate the cartesian of `param_grid` and backtest each combo.

    `param_grid` keys should be a subset of EmaAtrConfig fields. Missing keys
    fall back to `base_config` (default EmaAtrConfig())."""
    base = base_config or EmaAtrConfig()
    base_dict = _config_to_dict(base)
    keys = list(param_grid.keys())
    if not keys:
        return GridSearchResult(rows=[])

    rows: List[GridSearchRow] = []
    for combo_values in product(*(list(param_grid[k]) for k in keys)):
        combo = dict(zip(keys, combo_values))
        merged = {**base_dict, **combo}
        if merged["fast_ema"] >= merged["slow_ema"]:
            continue  # invalid: fast must be < slow
        try:
            config = EmaAtrConfig(**merged)
        except TypeError:
            continue

        def gen(symbol: str, bars: List[Candle], _cfg=config):
            return generate_ema_atr_signal(symbol, bars, _cfg)

        report = run_backtest(
            signal_generator=gen,
            candles_by_symbol=candles_by_symbol,
            initial_equity_usd=initial_equity_usd,
            risk_limits=risk_limits,
            risk_fraction=risk_fraction,
            allowed_symbols=allowed_symbols,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            min_bars_for_signal=min_bars_for_signal,
        )
        rows.append(GridSearchRow(params=combo, report=report))

    return GridSearchResult(rows=rows)



def _config_to_dict(config: EmaAtrConfig) -> Dict[str, Any]:
    return {
        "fast_ema": config.fast_ema,
        "slow_ema": config.slow_ema,
        "atr_period": config.atr_period,
        "atr_stop_mult": config.atr_stop_mult,
        "atr_tp_mult": config.atr_tp_mult,
        "leverage": config.leverage,
        "confidence": config.confidence,
        "expected_slippage_bps": config.expected_slippage_bps,
        "rationale": config.rationale,
    }



def _top_n_dict(data: Dict[str, int], n: int) -> Dict[str, int]:
    if not data:
        return {}
    return dict(sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:n])
