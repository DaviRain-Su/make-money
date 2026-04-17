from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    # 单合约名义金额上限（该合约已有敞口 + 新仓 notional）；0 = 关闭此检查。
    max_notional_per_symbol_usd: float = 0.0
    # 任何持仓距离强平 (|markPx - liqPx| / markPx) 小于该比例时，禁止开新仓。
    # 0 = 关闭此检查。例：0.1 表示离强平价 < 10% 就停止开新仓。
    min_liquidation_distance_pct: float = 0.0
    # 最多同时持有多少个合约；0 = 关闭此检查。加仓既有合约不受限。
    max_open_positions: int = 0


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
    # 按合约展开的敞口（instId → |notional_usd|）。None 表示未知（会跳过单合约风控）。
    positions_by_symbol: Optional[Dict[str, float]] = None
    # 每个持仓的详情（instId → {mark_px, liq_px, distance_pct, side, notional_usd}）。
    # None 表示未知，对应的强平距离风控会跳过。
    positions_detail: Optional[Dict[str, Dict[str, Any]]] = None


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
    # 可选的合约符号；payload 没传则由 main 层退化到 settings.okx_symbol。
    symbol: Optional[str] = None
