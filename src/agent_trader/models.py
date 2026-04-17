from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class RiskLimits:
    max_notional_usd: float
    max_leverage: float
    daily_loss_limit_pct: float
    max_slippage_bps: float
    min_equity_usd: float = 50.0
    trading_halted: bool = False


@dataclass(frozen=True)
class AccountState:
    equity_usd: float
    daily_pnl_pct: float
    current_exposure_usd: float
    open_positions: int


@dataclass(frozen=True)
class TradeProposal:
    connector: str
    symbol: str
    side: str
    notional_usd: float
    leverage: float
    expected_slippage_bps: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    position_action: str = "OPEN"
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    pos_side: str = ""


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategySignal:
    side: str
    confidence: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    expected_slippage_bps: float
    leverage: float
    rationale: str
    position_action: str = "OPEN"
    pos_side: str = ""
