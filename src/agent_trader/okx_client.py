from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class OKXCredentials:
    api_key: str
    api_secret: str
    passphrase: str
    flag: str = "1"


class OKXClient:
    def __init__(
        self,
        account_api: Any,
        trade_api: Any,
        market_api: Any,
        public_api: Any = None,
        td_mode: str = "cross",
    ):
        self.account_api = account_api
        self.trade_api = trade_api
        self.market_api = market_api
        self.public_api = public_api
        self.td_mode = td_mode
        self._account_config_cache: Optional[Dict[str, Any]] = None
        self._instrument_cache: Dict[str, Dict[str, Any]] = {}
        self._leverage_cache: Dict[Tuple[str, str, str], str] = {}

    @classmethod
    def from_credentials(
        cls,
        credentials: OKXCredentials,
        td_mode: str = "cross",
        debug: bool = False,
    ) -> "OKXClient":
        try:
            import okx.Account as Account
            import okx.Trade as Trade
            import okx.MarketData as MarketData
            import okx.PublicData as PublicData
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("python-okx is not installed") from exc

        account_api = Account.AccountAPI(
            api_key=credentials.api_key,
            api_secret_key=credentials.api_secret,
            passphrase=credentials.passphrase,
            flag=credentials.flag,
            debug=debug,
        )
        trade_api = Trade.TradeAPI(
            api_key=credentials.api_key,
            api_secret_key=credentials.api_secret,
            passphrase=credentials.passphrase,
            flag=credentials.flag,
            debug=debug,
        )
        market_api = MarketData.MarketAPI(flag=credentials.flag, debug=debug)
        public_api = PublicData.PublicAPI(flag=credentials.flag, debug=debug)
        return cls(
            account_api=account_api,
            trade_api=trade_api,
            market_api=market_api,
            public_api=public_api,
            td_mode=td_mode,
        )

    def get_account_balance(self, ccy: str = "USDT") -> Any:
        return self.account_api.get_account_balance(ccy=ccy)

    def get_positions(self, inst_id: str = "") -> Any:
        if inst_id:
            return self.account_api.get_positions(instType="SWAP", instId=inst_id, posId="")
        return self.account_api.get_positions(instType="SWAP", instId="", posId="")

    def get_account_bills(self, inst_type: str = "SWAP", ccy: str = "USDT", limit: str = "100") -> Any:
        return self.account_api.get_account_bills(instType=inst_type, ccy=ccy, limit=limit)

    def get_order(self, inst_id: str, order_id: str) -> Any:
        return self.trade_api.get_order(instId=inst_id, ordId=order_id, clOrdId="")

    def get_account_config(self, refresh: bool = False) -> Dict[str, Any]:
        if self._account_config_cache is None or refresh:
            self._account_config_cache = self.account_api.get_account_config()
        return self._account_config_cache

    def get_position_mode(self, refresh: bool = False) -> str:
        config = self.get_account_config(refresh=refresh)
        rows = config.get("data", []) if isinstance(config, dict) else []
        if not rows:
            return "net_mode"
        return rows[0].get("posMode", "net_mode")

    def get_instrument(self, inst_id: str) -> Dict[str, Any]:
        if inst_id not in self._instrument_cache:
            if self.public_api is None:
                raise RuntimeError("OKX public API client is not configured")
            response = self.public_api.get_instruments(instType="SWAP", instId=inst_id)
            rows = response.get("data", []) if isinstance(response, dict) else []
            if not rows:
                raise ValueError(f"No instrument metadata returned for {inst_id}")
            self._instrument_cache[inst_id] = rows[0]
        return self._instrument_cache[inst_id]

    def get_contract_value(self, inst_id: str) -> float:
        instrument = self.get_instrument(inst_id)
        ct_val = instrument.get("ctVal")
        if ct_val in (None, ""):
            raise ValueError(f"Instrument {inst_id} missing ctVal")
        return float(ct_val)

    def get_last_price(self, inst_id: str) -> float:
        response = self.market_api.get_ticker(inst_id)
        data = response.get("data", [])
        if not data:
            raise ValueError(f"No ticker data returned for {inst_id}")
        return float(data[0]["last"])

    def _resolve_pos_side(self, side: str, pos_side: str = "") -> str:
        if pos_side:
            return pos_side
        position_mode = self.get_position_mode()
        if position_mode == "long_short_mode":
            return "long" if side.lower() == "buy" else "short"
        return ""

    def set_leverage(self, inst_id: str, leverage: float, pos_side: str = "") -> Any:
        leverage_str = str(int(leverage)) if float(leverage).is_integer() else str(leverage)
        resolved_pos_side = pos_side
        cache_key = (inst_id, self.td_mode, resolved_pos_side)
        if self._leverage_cache.get(cache_key) == leverage_str:
            return {"code": "0", "data": [{"lever": leverage_str}], "cached": True}
        response = self.account_api.set_leverage(
            lever=leverage_str,
            mgnMode=self.td_mode,
            instId=inst_id,
            ccy="",
            posSide=resolved_pos_side,
        )
        self._leverage_cache[cache_key] = leverage_str
        return response

    def place_market_order(
        self,
        inst_id: str,
        side: str,
        size: str,
        leverage: float,
        reduce_only: bool,
        pos_side: str = "",
        attach_algo_ords: Optional[list] = None,
    ) -> Any:
        resolved_pos_side = self._resolve_pos_side(side=side, pos_side=pos_side)
        self.set_leverage(inst_id=inst_id, leverage=leverage, pos_side=resolved_pos_side)
        params = {
            "instId": inst_id,
            "tdMode": self.td_mode,
            "side": side,
            "ordType": "market",
            "sz": size,
            "reduceOnly": reduce_only,
        }
        if resolved_pos_side:
            params["posSide"] = resolved_pos_side
        if attach_algo_ords:
            params["attachAlgoOrds"] = attach_algo_ords
        return self.trade_api.place_order(**params)
