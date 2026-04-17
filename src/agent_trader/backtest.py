"""Walk-forward backtester that reuses our production risk engine.

The goal is NOT "find alpha" (freqtrade's backtester is better for that) but
"tell me which candidate strategies my risk engine would actually let through
in production, and what the hypothetical PnL of the ones that pass looks
like." Every signal gets routed through `evaluate_trade` with a simulated
`AccountState`, so risk rules that would block in prod also block here.

Assumptions (kept deliberately simple for v1):
- Fills happen at the signal bar's close price (with configurable slippage).
- SL/TP are evaluated against each subsequent bar's high/low. If both could
  trigger in the same bar, SL wins (conservative).
- One open position per symbol at a time. A second signal on an already-open
  symbol is ignored (not closed-then-reopened).
- No funding fees; a flat fee in bps is charged on both entry and exit.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from agent_trader.models import AccountState, RiskLimits, StrategySignal, TradeProposal
from agent_trader.risk import evaluate_trade
from agent_trader.strategy import Candle


SignalGenerator = Callable[[str, List[Candle]], Optional[StrategySignal]]



@dataclass
class OpenPosition:
    symbol: str
    side: str
    notional_usd: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    leverage: float
    entered_at: int



@dataclass
class ClosedTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    stop_loss_price: float
    take_profit_price: float
    notional_usd: float
    entered_at: int
    exited_at: int
    exit_reason: str   # "stop_loss" | "take_profit" | "end_of_data"
    pnl_usd: float
    pnl_pct: float



@dataclass
class BlockedSignal:
    ts: int
    symbol: str
    side: str
    reasons: List[str]



@dataclass
class BacktestReport:
    initial_equity_usd: float
    final_equity_usd: float
    signals_total: int
    signals_approved: int
    signals_blocked: int
    block_reasons: Dict[str, int]
    closed_trades: List[ClosedTrade]
    blocked_signals: List[BlockedSignal]

    @property
    def total_pnl_usd(self) -> float:
        return sum(t.pnl_usd for t in self.closed_trades)

    @property
    def trades_won(self) -> int:
        return sum(1 for t in self.closed_trades if t.pnl_usd > 0)

    @property
    def trades_lost(self) -> int:
        return sum(1 for t in self.closed_trades if t.pnl_usd <= 0)

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        return self.trades_won / len(self.closed_trades)

    @property
    def max_drawdown_pct(self) -> float:
        peak = self.initial_equity_usd
        running = self.initial_equity_usd
        worst = 0.0
        for trade in sorted(self.closed_trades, key=lambda t: t.exited_at):
            running += trade.pnl_usd
            peak = max(peak, running)
            if peak > 0:
                dd = (peak - running) / peak
                worst = max(worst, dd)
        return worst



def run_backtest(
    signal_generator: SignalGenerator,
    candles_by_symbol: Dict[str, List[Candle]],
    initial_equity_usd: float,
    risk_limits: RiskLimits,
    risk_fraction: float = 0.1,
    allowed_symbols: Optional[Iterable[str]] = None,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    min_bars_for_signal: int = 30,
) -> BacktestReport:
    """Walk forward across every bar timestamp across every symbol."""
    if initial_equity_usd <= 0:
        raise ValueError("initial_equity_usd must be positive")

    symbols = list(candles_by_symbol.keys())
    candles_by_symbol = {s: sorted(c, key=lambda b: b.ts) for s, c in candles_by_symbol.items()}

    # Union of all bar timestamps, ascending.
    timestamps = sorted({c.ts for candles in candles_by_symbol.values() for c in candles})

    # Index helper: for symbol, map ts -> index (fast bar lookup).
    index_by_symbol: Dict[str, Dict[int, int]] = {
        sym: {c.ts: i for i, c in enumerate(candles)} for sym, candles in candles_by_symbol.items()
    }

    equity = initial_equity_usd
    open_positions: Dict[str, OpenPosition] = {}
    closed_trades: List[ClosedTrade] = []
    blocked_signals: List[BlockedSignal] = []
    block_reasons: Dict[str, int] = {}
    signals_total = 0
    signals_approved = 0
    fee_multiplier = fee_bps / 10_000.0
    slippage_multiplier = slippage_bps / 10_000.0

    for ts in timestamps:
        # 1. Close any open positions whose SL/TP triggered this bar.
        for sym in list(open_positions.keys()):
            position = open_positions[sym]
            idx = index_by_symbol[sym].get(ts)
            if idx is None:
                continue
            bar = candles_by_symbol[sym][idx]
            exit_price, reason = _check_exit(position, bar)
            if exit_price is None:
                continue
            pnl = _compute_pnl(position, exit_price, fee_multiplier)
            equity += pnl
            closed_trades.append(
                ClosedTrade(
                    symbol=sym,
                    side=position.side,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    stop_loss_price=position.stop_loss_price,
                    take_profit_price=position.take_profit_price,
                    notional_usd=position.notional_usd,
                    entered_at=position.entered_at,
                    exited_at=bar.ts,
                    exit_reason=reason,
                    pnl_usd=pnl,
                    pnl_pct=(pnl / position.notional_usd) * 100.0 if position.notional_usd > 0 else 0.0,
                )
            )
            del open_positions[sym]

        # 2. For each symbol with a closed bar at this ts and no existing
        #    position, ask the strategy whether to enter.
        for sym in symbols:
            idx = index_by_symbol[sym].get(ts)
            if idx is None or idx < min_bars_for_signal:
                continue
            if sym in open_positions:
                continue  # already in a trade on this symbol
            candles_so_far = candles_by_symbol[sym][: idx + 1]
            signal = signal_generator(sym, candles_so_far)
            if signal is None:
                continue
            signals_total += 1
            entry_price = candles_so_far[-1].close
            notional = _sizing(equity, risk_fraction, signal, risk_limits, open_positions)
            proposal = _proposal_from_signal(signal, notional)
            account = _simulate_account(equity, open_positions)
            decision = evaluate_trade(
                proposal, account, risk_limits, allowed_symbols=allowed_symbols
            )
            if not decision.approved:
                blocked_signals.append(
                    BlockedSignal(ts=ts, symbol=sym, side=signal.side, reasons=list(decision.reasons))
                )
                for reason in decision.reasons:
                    block_reasons[reason] = block_reasons.get(reason, 0) + 1
                continue
            if proposal.notional_usd <= 0:
                continue  # sizing zeroed out, skip
            signals_approved += 1
            # Open the position with fee/slippage on entry price.
            filled_entry = entry_price * (1 + slippage_multiplier if signal.side == "buy" else 1 - slippage_multiplier)
            open_positions[sym] = OpenPosition(
                symbol=sym,
                side=signal.side,
                notional_usd=proposal.notional_usd,
                entry_price=filled_entry,
                stop_loss_price=signal.stop_loss_price,
                take_profit_price=signal.take_profit_price,
                leverage=proposal.leverage,
                entered_at=ts,
            )
            equity -= proposal.notional_usd * fee_multiplier  # entry fee

    # 3. Force-close whatever's still open at the last bar's close.
    for sym, position in list(open_positions.items()):
        last_bar = candles_by_symbol[sym][-1]
        pnl = _compute_pnl(position, last_bar.close, fee_multiplier)
        equity += pnl
        closed_trades.append(
            ClosedTrade(
                symbol=sym,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=last_bar.close,
                stop_loss_price=position.stop_loss_price,
                take_profit_price=position.take_profit_price,
                notional_usd=position.notional_usd,
                entered_at=position.entered_at,
                exited_at=last_bar.ts,
                exit_reason="end_of_data",
                pnl_usd=pnl,
                pnl_pct=(pnl / position.notional_usd) * 100.0 if position.notional_usd > 0 else 0.0,
            )
        )

    return BacktestReport(
        initial_equity_usd=initial_equity_usd,
        final_equity_usd=equity,
        signals_total=signals_total,
        signals_approved=signals_approved,
        signals_blocked=len(blocked_signals),
        block_reasons=block_reasons,
        closed_trades=closed_trades,
        blocked_signals=blocked_signals,
    )



def _check_exit(position: OpenPosition, bar: Candle):
    """Return (exit_price, reason) if SL or TP triggered this bar, else (None, '')."""
    if position.side == "buy":
        hit_sl = bar.low <= position.stop_loss_price
        hit_tp = bar.high >= position.take_profit_price
    else:
        hit_sl = bar.high >= position.stop_loss_price
        hit_tp = bar.low <= position.take_profit_price
    if hit_sl and hit_tp:
        return position.stop_loss_price, "stop_loss"  # conservative: stop first
    if hit_sl:
        return position.stop_loss_price, "stop_loss"
    if hit_tp:
        return position.take_profit_price, "take_profit"
    return None, ""



def _compute_pnl(position: OpenPosition, exit_price: float, fee_multiplier: float) -> float:
    if position.entry_price <= 0:
        return 0.0
    if position.side == "buy":
        gross = (exit_price - position.entry_price) / position.entry_price * position.notional_usd
    else:
        gross = (position.entry_price - exit_price) / position.entry_price * position.notional_usd
    exit_fee = position.notional_usd * fee_multiplier
    return gross - exit_fee



def _sizing(
    equity: float,
    risk_fraction: float,
    signal: StrategySignal,
    risk_limits: RiskLimits,
    open_positions: Dict[str, OpenPosition],
) -> float:
    """Simple sizing: equity * fraction, capped by risk limits."""
    budget = equity * max(risk_fraction, 0.0)
    current_exposure = sum(p.notional_usd for p in open_positions.values())
    remaining_global = max(risk_limits.max_notional_usd - current_exposure, 0.0)
    candidate = min(budget, remaining_global)
    if risk_limits.max_notional_per_symbol_usd > 0:
        existing_on_symbol = sum(p.notional_usd for p in open_positions.values() if p.symbol == signal.symbol)
        remaining_symbol = max(risk_limits.max_notional_per_symbol_usd - existing_on_symbol, 0.0)
        candidate = min(candidate, remaining_symbol)
    return round(candidate, 8)



def _proposal_from_signal(signal: StrategySignal, notional_usd: float) -> TradeProposal:
    return TradeProposal(
        connector="okx_native",
        symbol=signal.symbol or "",
        side=signal.side.lower(),
        notional_usd=notional_usd,
        leverage=max(signal.leverage, 1.0),
        expected_slippage_bps=signal.expected_slippage_bps,
        order_type="MARKET",
        position_action="OPEN",
        stop_loss_price=signal.stop_loss_price,
        take_profit_price=signal.take_profit_price,
    )



def _simulate_account(equity: float, open_positions: Dict[str, OpenPosition]) -> AccountState:
    exposure = sum(p.notional_usd for p in open_positions.values())
    positions_by_symbol = {
        sym: sum(p.notional_usd for p in open_positions.values() if p.symbol == sym)
        for sym in {p.symbol for p in open_positions.values()}
    } or None
    return AccountState(
        equity_usd=max(equity, 0.0),
        daily_pnl_pct=0.0,
        current_exposure_usd=exposure,
        open_positions=len(open_positions),
        positions_by_symbol=positions_by_symbol,
    )
