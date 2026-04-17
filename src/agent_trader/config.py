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
        ),
    )
