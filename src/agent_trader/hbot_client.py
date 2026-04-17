import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from urllib import parse, request


class Transport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        ...


@dataclass
class UrllibTransport:
    base_url: str
    username: str
    password: str
    timeout: float = 30.0

    def request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = self._build_url(path, params)
        headers = self._headers(json_body)
        data = None if json_body is None else json.dumps(json_body).encode("utf-8")
        req = request.Request(url=url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)

    def _build_url(self, path: str, params: Optional[Dict[str, Any]]) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url.rstrip('/')}{normalized_path}"
        if not params:
            return url
        filtered = {key: value for key, value in params.items() if value is not None}
        if not filtered:
            return url
        return f"{url}?{parse.urlencode(filtered, doseq=True)}"

    def _headers(self, json_body: Optional[Dict[str, Any]]) -> Dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        return headers


class HummingbotClient:
    def __init__(self, transport: Transport):
        self.transport = transport

    def get_portfolio_state(
        self,
        account_names: Optional[List[str]] = None,
        connector_names: Optional[List[str]] = None,
        refresh: bool = False,
        skip_gateway: bool = False,
    ) -> Any:
        body: Dict[str, Any] = {}
        if account_names is not None:
            body["account_names"] = account_names
        if connector_names is not None:
            body["connector_names"] = connector_names
        if refresh:
            body["refresh"] = True
        if skip_gateway:
            body["skip_gateway"] = True
        return self.transport.request("POST", "/portfolio/state", json_body=body or None)

    def get_portfolio_history(
        self,
        account_names: Optional[List[str]] = None,
        connector_names: Optional[List[str]] = None,
        limit: int = 2,
        interval: str = "1d",
    ) -> Any:
        body: Dict[str, Any] = {"limit": limit, "interval": interval}
        if account_names is not None:
            body["account_names"] = account_names
        if connector_names is not None:
            body["connector_names"] = connector_names
        return self.transport.request("POST", "/portfolio/history", json_body=body)

    def get_positions(
        self,
        account_names: Optional[List[str]] = None,
        connector_names: Optional[List[str]] = None,
        limit: int = 50,
    ) -> Any:
        body: Dict[str, Any] = {"limit": limit}
        if account_names is not None:
            body["account_names"] = account_names
        if connector_names is not None:
            body["connector_names"] = connector_names
        return self.transport.request("POST", "/trading/positions", json_body=body)

    def set_leverage(
        self,
        account_name: str,
        connector_name: str,
        trading_pair: str,
        leverage: float,
    ) -> Any:
        return self.transport.request(
            "POST",
            f"/trading/{account_name}/{connector_name}/leverage",
            json_body={"trading_pair": trading_pair, "leverage": leverage},
        )

    def place_order(
        self,
        account_name: str,
        connector_name: str,
        trading_pair: str,
        trade_type: str,
        amount: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        position_action: str = "OPEN",
    ) -> Any:
        body: Dict[str, Any] = {
            "account_name": account_name,
            "connector_name": connector_name,
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "amount": amount,
            "order_type": order_type,
            "position_action": position_action,
        }
        if price is not None:
            body["price"] = price
        return self.transport.request("POST", "/trading/orders", json_body=body)

    def list_connectors(self) -> Any:
        return self.transport.request("GET", "/connectors/")

    def list_accounts(self) -> Any:
        return self.transport.request("GET", "/accounts/")
