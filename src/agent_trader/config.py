from dataclasses import dataclass
from typing import Tuple
import os

from agent_trader.models import RiskLimits

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    environment: str
    okx_connector_id: str
    okx_symbol: str
    okx_api_key: str
    okx_api_secret: str
    okx_passphrase: str
    okx_flag: str
    okx_td_mode: str
    okx_ws_url: str
    reconcile_poll_interval_seconds: int
    use_okx_native: bool
    hbot_account_name: str
    hbot_api_url: str
    hbot_api_username: str
    hbot_api_password: str
    execution_enabled: bool
    paper_mode: bool
    proposal_risk_fraction: float
    audit_log_path: str
    signal_shared_secret: str
    signal_idempotency_path: str
    control_state_path: str
    admin_shared_secret: str
    admin_nonce_path: str
    admin_small_trade_usd: float
    admin_large_trade_usd: float
    risk_limits: RiskLimits
    okx_allowed_symbols: Tuple[str, ...] = ()
    # 策略信号源（EMA/ATR）相关
    strategy_enabled: bool = False
    strategy_symbols: Tuple[str, ...] = ()          # 空 = 用 okx_allowed_symbols，再空 = [okx_symbol]
    strategy_bar: str = "1H"
    strategy_candle_limit: int = 200
    strategy_poll_seconds: int = 300
    strategy_fast_ema: int = 20
    strategy_slow_ema: int = 50
    strategy_atr_period: int = 14
    strategy_atr_stop_mult: float = 2.0
    strategy_atr_tp_mult: float = 3.0
    strategy_leverage: float = 2.0
    strategy_confidence: float = 0.6
    strategy_expected_slippage_bps: float = 8.0
    # 多时间周期共振过滤；higher_tf_slow_ema=0 关闭
    strategy_higher_tf_bar: str = ""
    strategy_higher_tf_slow_ema: int = 0
    # 信号生成器名字（对应 signal_registry 里注册的 key）；
    # 空 = 用默认的内置 ema_atr 参数路径
    strategy_generator: str = ""
    # 同方向已有持仓时跳过新信号（防止一路加仓追高）
    strategy_skip_same_direction: bool = True
    # 反向信号遇到既有持仓时的处理：
    # "open"       = 允许翻仓（历史行为；直接开反向仓）
    # "close_only" = 只平仓不反手（更保守：等下一根确认再考虑开新仓）
    strategy_reverse_signal_mode: str = "open"
    # freqtrade 反向 adapter
    freqtrade_api_url: str = ""
    freqtrade_api_username: str = ""
    freqtrade_api_password: str = ""
    freqtrade_reconcile_on_block: bool = False
    # 告警 webhook（为空则全关）
    alert_webhook_url: str = ""
    alert_timeout_seconds: float = 5.0
    monitor_snapshot_path: str = "var/state/monitor_snapshot.json"
    monitor_poll_seconds: int = 60
    # 山寨币筛选观察池
    strategy_alt_screener_enabled: bool = False
    strategy_alt_top_n: int = 10
    strategy_alt_min_change_pct: float = 1.0
    strategy_alt_min_volume_24h: float = 5_000_000.0
    strategy_alt_exclude_symbols: Tuple[str, ...] = ()



def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default



def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default



def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}



def _tuple_env(name: str) -> Tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return ()
    return tuple(token.strip() for token in value.split(",") if token.strip())



def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "dev"),
        okx_connector_id=os.getenv("OKX_CONNECTOR_ID", "okx_perpetual"),
        okx_symbol=os.getenv("OKX_SYMBOL", "BTC-USDT-SWAP"),
        okx_allowed_symbols=_tuple_env("OKX_ALLOWED_SYMBOLS"),
        okx_api_key=os.getenv("OKX_API_KEY", ""),
        okx_api_secret=os.getenv("OKX_API_SECRET", ""),
        okx_passphrase=os.getenv("OKX_PASSPHRASE", ""),
        okx_flag=os.getenv("OKX_FLAG", "1"),
        okx_td_mode=os.getenv("OKX_TD_MODE", "cross"),
        okx_ws_url=os.getenv("OKX_WS_URL", "wss://ws.okx.com:8443/ws/v5/private"),
        reconcile_poll_interval_seconds=_int_env("RECONCILE_POLL_INTERVAL_SECONDS", 30),
        use_okx_native=_bool_env("USE_OKX_NATIVE", True),
        hbot_account_name=os.getenv("HBOT_ACCOUNT_NAME", "primary"),
        hbot_api_url=os.getenv("HBOT_API_URL", "http://localhost:8000"),
        hbot_api_username=os.getenv("HBOT_API_USERNAME", "admin"),
        hbot_api_password=os.getenv("HBOT_API_PASSWORD", "admin"),
        execution_enabled=_bool_env("EXECUTION_ENABLED", False),
        paper_mode=_bool_env("PAPER_MODE", True),
        proposal_risk_fraction=_float_env("PROPOSAL_RISK_FRACTION", 0.1),
        audit_log_path=os.getenv("AUDIT_LOG_PATH", "var/logs/audit/events.jsonl"),
        signal_shared_secret=os.getenv("SIGNAL_SHARED_SECRET", ""),
        signal_idempotency_path=os.getenv("SIGNAL_IDEMPOTENCY_PATH", "var/state/signal_ids.txt"),
        control_state_path=os.getenv("CONTROL_STATE_PATH", "var/state/control.json"),
        admin_shared_secret=os.getenv("ADMIN_SHARED_SECRET", ""),
        admin_nonce_path=os.getenv("ADMIN_NONCE_PATH", "var/state/admin_nonces.txt"),
        admin_small_trade_usd=_float_env("ADMIN_SMALL_TRADE_USD", 500.0),
        admin_large_trade_usd=_float_env("ADMIN_LARGE_TRADE_USD", 5000.0),
        risk_limits=RiskLimits(
            max_notional_usd=_float_env("RISK_MAX_NOTIONAL_USD", 1000.0),
            max_leverage=_float_env("RISK_MAX_LEVERAGE", 3.0),
            daily_loss_limit_pct=_float_env("RISK_DAILY_LOSS_LIMIT_PCT", 2.0),
            max_slippage_bps=_float_env("RISK_MAX_SLIPPAGE_BPS", 15.0),
            min_equity_usd=_float_env("RISK_MIN_EQUITY_USD", 50.0),
            trading_halted=_bool_env("TRADING_HALTED", False),
            min_margin_ratio=_float_env("RISK_MIN_MARGIN_RATIO", 0.0),
            max_margin_utilization=_float_env("RISK_MAX_MARGIN_UTILIZATION", 1.0),
            min_available_equity_usd=_float_env("RISK_MIN_AVAIL_EQUITY_USD", 0.0),
            max_notional_per_symbol_usd=_float_env("RISK_MAX_NOTIONAL_PER_SYMBOL_USD", 0.0),
            min_liquidation_distance_pct=_float_env("RISK_MIN_LIQUIDATION_DISTANCE_PCT", 0.0),
            max_open_positions=_int_env("RISK_MAX_OPEN_POSITIONS", 0),
        ),
        strategy_enabled=_bool_env("STRATEGY_ENABLED", False),
        strategy_symbols=_tuple_env("STRATEGY_SYMBOLS"),
        strategy_bar=os.getenv("STRATEGY_BAR", "1H"),
        strategy_candle_limit=_int_env("STRATEGY_CANDLE_LIMIT", 200),
        strategy_poll_seconds=_int_env("STRATEGY_POLL_SECONDS", 300),
        strategy_fast_ema=_int_env("STRATEGY_FAST_EMA", 20),
        strategy_slow_ema=_int_env("STRATEGY_SLOW_EMA", 50),
        strategy_atr_period=_int_env("STRATEGY_ATR_PERIOD", 14),
        strategy_atr_stop_mult=_float_env("STRATEGY_ATR_STOP_MULT", 2.0),
        strategy_atr_tp_mult=_float_env("STRATEGY_ATR_TP_MULT", 3.0),
        strategy_leverage=_float_env("STRATEGY_LEVERAGE", 2.0),
        strategy_confidence=_float_env("STRATEGY_CONFIDENCE", 0.6),
        strategy_expected_slippage_bps=_float_env("STRATEGY_EXPECTED_SLIPPAGE_BPS", 8.0),
        strategy_higher_tf_bar=os.getenv("STRATEGY_HIGHER_TF_BAR", ""),
        strategy_higher_tf_slow_ema=_int_env("STRATEGY_HIGHER_TF_SLOW_EMA", 0),
        strategy_generator=os.getenv("STRATEGY_GENERATOR", ""),
        strategy_skip_same_direction=_bool_env("STRATEGY_SKIP_SAME_DIRECTION", True),
        strategy_reverse_signal_mode=os.getenv("STRATEGY_REVERSE_SIGNAL_MODE", "open"),
        freqtrade_api_url=os.getenv("FREQTRADE_API_URL", ""),
        freqtrade_api_username=os.getenv("FREQTRADE_API_USERNAME", ""),
        freqtrade_api_password=os.getenv("FREQTRADE_API_PASSWORD", ""),
        freqtrade_reconcile_on_block=_bool_env("FREQTRADE_RECONCILE_ON_BLOCK", False),
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
        alert_timeout_seconds=_float_env("ALERT_TIMEOUT_SECONDS", 5.0),
        monitor_snapshot_path=os.getenv("MONITOR_SNAPSHOT_PATH", "var/state/monitor_snapshot.json"),
        monitor_poll_seconds=_int_env("MONITOR_POLL_SECONDS", 60),
        strategy_alt_screener_enabled=_bool_env("STRATEGY_ALT_SCREENER_ENABLED", False),
        strategy_alt_top_n=_int_env("STRATEGY_ALT_TOP_N", 10),
        strategy_alt_min_change_pct=_float_env("STRATEGY_ALT_MIN_CHANGE_PCT", 1.0),
        strategy_alt_min_volume_24h=_float_env("STRATEGY_ALT_MIN_VOLUME_24H", 5_000_000.0),
        strategy_alt_exclude_symbols=_tuple_env("STRATEGY_ALT_EXCLUDE_SYMBOLS"),
    )
