import unittest

from agent_trader.okx_client import OKXClient


class FakeAccountAPI:
    def __init__(self):
        self.calls = []

    def get_account_balance(self, ccy=''):
        self.calls.append(("get_account_balance", ccy))
        return {"code": "0", "data": [{"totalEq": "1500"}]}

    def get_positions(self, instType='', instId='', posId=''):
        self.calls.append(("get_positions", instType, instId, posId))
        return {"code": "0", "data": [{"instId": instId, "notionalUsd": "250"}]}

    def get_account_bills(self, instType='SWAP', ccy='USDT', limit='100'):
        self.calls.append(("get_account_bills", instType, ccy, limit))
        return {"code": "0", "data": []}

    def get_account_config(self):
        self.calls.append(("get_account_config",))
        return {"code": "0", "data": [{"posMode": "long_short_mode"}]}

    def set_leverage(self, lever, mgnMode, instId='', ccy='', posSide=''):
        self.calls.append(("set_leverage", lever, mgnMode, instId, ccy, posSide))
        return {"code": "0", "data": [{"lever": lever}]}


class FakeTradeAPI:
    def __init__(self):
        self.calls = []

    def place_order(self, **kwargs):
        self.calls.append(("place_order", kwargs))
        return {"code": "0", "data": [{"ordId": "12345"}]}

    def get_order(self, instId, ordId='', clOrdId=''):
        self.calls.append(("get_order", instId, ordId, clOrdId))
        return {"code": "0", "data": [{"ordId": ordId, "state": "live"}]}


class FakeMarketAPI:
    def __init__(self):
        self.calls = []

    def get_ticker(self, instId):
        self.calls.append(("get_ticker", instId))
        return {"code": "0", "data": [{"instId": instId, "last": "50000"}]}


class FakePublicAPI:
    def __init__(self):
        self.calls = []

    def get_instruments(self, instType, instId='', uly='', instFamily=''):
        self.calls.append(("get_instruments", instType, instId, uly, instFamily))
        return {"code": "0", "data": [{"instId": instId, "ctVal": "0.01"}]}


class OKXClientTests(unittest.TestCase):
    def setUp(self):
        self.account_api = FakeAccountAPI()
        self.trade_api = FakeTradeAPI()
        self.market_api = FakeMarketAPI()
        self.public_api = FakePublicAPI()
        self.client = OKXClient(
            account_api=self.account_api,
            trade_api=self.trade_api,
            market_api=self.market_api,
            public_api=self.public_api,
            td_mode="cross",
        )

    def test_get_account_balance_delegates_to_sdk(self):
        response = self.client.get_account_balance("USDT")
        self.assertEqual(response["code"], "0")
        self.assertEqual(self.account_api.calls[0], ("get_account_balance", "USDT"))

    def test_get_positions_requests_swap_instrument(self):
        response = self.client.get_positions("BTC-USDT-SWAP")
        self.assertEqual(response["code"], "0")
        self.assertEqual(self.account_api.calls[0], ("get_positions", "SWAP", "BTC-USDT-SWAP", ""))

    def test_get_last_price_reads_ticker(self):
        price = self.client.get_last_price("BTC-USDT-SWAP")
        self.assertEqual(price, 50000.0)
        self.assertEqual(self.market_api.calls[0], ("get_ticker", "BTC-USDT-SWAP"))

    def test_get_order_delegates_to_sdk(self):
        response = self.client.get_order("BTC-USDT-SWAP", "123")
        self.assertEqual(response["data"][0]["ordId"], "123")
        self.assertEqual(self.trade_api.calls[0], ("get_order", "BTC-USDT-SWAP", "123", ""))

    def test_get_contract_value_reads_instrument_metadata(self):
        value = self.client.get_contract_value("BTC-USDT-SWAP")
        self.assertEqual(value, 0.01)
        self.assertEqual(self.public_api.calls[0], ("get_instruments", "SWAP", "BTC-USDT-SWAP", "", ""))

    def test_place_market_order_sets_pos_side_and_caches_leverage(self):
        first = self.client.place_market_order(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            size="2",
            leverage=3,
            reduce_only=False,
            attach_algo_ords=[{"slTriggerPx": "49000", "slOrdPx": "-1"}],
        )
        second = self.client.place_market_order(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            size="2",
            leverage=3,
            reduce_only=False,
        )
        self.assertEqual(first["data"][0]["ordId"], "12345")
        self.assertEqual(second["data"][0]["ordId"], "12345")
        self.assertEqual(
            self.account_api.calls.count(("set_leverage", "3", "cross", "BTC-USDT-SWAP", "", "long")),
            1,
        )
        self.assertEqual(
            self.trade_api.calls[0],
            (
                "place_order",
                {
                    "instId": "BTC-USDT-SWAP",
                    "tdMode": "cross",
                    "side": "buy",
                    "ordType": "market",
                    "sz": "2",
                    "reduceOnly": False,
                    "posSide": "long",
                    "attachAlgoOrds": [{"slTriggerPx": "49000", "slOrdPx": "-1"}],
                },
            ),
        )


if __name__ == "__main__":
    unittest.main()
