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
    # 低于该保证金率视为接近爆仓；0 = 关闭此检查。
    min_margin_ratio: float = 0.0
    # (已用保证金 + 新仓初始保证金) / 总权益 超过该值拒单；1.0 = 关闭此检查。
    max_margin_utilization: float = 1.0
    # 可用保证金低于该值拒单；0 = 关闭此检查。
    min_available_equity_usd: float = 0.0


@dataclass(frozen=True)
class AccountState:
    equity_usd: float
    daily_pnl_pct: float
    current_exposure_usd: float
    open_positions: int
    # 可用保证金（OKX availEq）。None 表示未知 / 未采样，对应的风控检查会跳过。
    available_equity_usd: Optional[float] = None
    # 账户级保证金率（OKX mgnRatio）。None 表示未知。
    margin_ratio: Optional[float] = None
    # 已用初始保证金（OKX imr）。None 表示未知。
    used_margin_usd: Optional[float] = None


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
