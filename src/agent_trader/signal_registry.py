"""Pluggable signal-generator registry.

A signal generator is just a callable:
    (symbol, primary_candles, higher_tf_candles=None) -> Optional[StrategySignal]

Users plug in new strategies (rule-based, ML-scored, external service) by
registering a named generator here. The strategy runner looks up by name so
no changes to core code are needed to try a new approach. Built-in entry is
`ema_atr`; alternatives can live in this repo or be registered at runtime
from user code.

Deliberately tiny — no dynamic import, no entry-point magic. If you want to
register a generator defined outside the package, just call `register(...)`
before the first `run_strategy_poll`.
"""

from typing import Callable, Dict, List, Optional

from agent_trader.models import StrategySignal
from agent_trader.strategy import Candle, EmaAtrConfig, generate_ema_atr_signal


SignalGeneratorFn = Callable[[str, List[Candle], Optional[List[Candle]]], Optional[StrategySignal]]


_REGISTRY: Dict[str, SignalGeneratorFn] = {}



def register(name: str, generator: SignalGeneratorFn) -> None:
    if not name:
        raise ValueError("name required")
    _REGISTRY[name] = generator



def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)



def available() -> List[str]:
    return sorted(_REGISTRY.keys())



def resolve(name: str) -> SignalGeneratorFn:
    if name not in _REGISTRY:
        raise KeyError(
            f"signal generator {name!r} not registered. Available: {available()}"
        )
    return _REGISTRY[name]



def _ema_atr_generator_factory(config: EmaAtrConfig) -> SignalGeneratorFn:
    def generator(symbol: str, candles: List[Candle], higher_tf: Optional[List[Candle]] = None) -> Optional[StrategySignal]:
        return generate_ema_atr_signal(symbol, candles, config, higher_tf_candles=higher_tf)
    return generator



def register_ema_atr(name: str = "ema_atr", config: Optional[EmaAtrConfig] = None) -> None:
    """Convenience registration for the built-in EMA/ATR generator. Called
    automatically once when this module is imported, with default config."""
    register(name, _ema_atr_generator_factory(config or EmaAtrConfig()))



# Register the built-in with default config on import so callers can resolve
# "ema_atr" without any extra setup.
register_ema_atr()
