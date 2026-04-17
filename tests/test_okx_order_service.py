import unittest

from agent_trader.okx_order_service import reconcile_order_status


class FakeOKXClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_order(self, inst_id, order_id):
        self.calls.append((inst_id, order_id))
        return self.response


class OKXOrderServiceTests(unittest.TestCase):
    def test_reconcile_order_status_maps_okx_payload(self):
        client = FakeOKXClient(
            {
                "code": "0",
                "data": [
                    {
                        "ordId": "123",
                        "state": "filled",
                        "fillSz": "0.01",
                        "avgPx": "50100",
                        "instId": "BTC-USDT-SWAP",
                        "side": "buy",
                    }
                ],
            }
        )

        result = reconcile_order_status(client, "BTC-USDT-SWAP", "123")

        self.assertEqual(client.calls[0], ("BTC-USDT-SWAP", "123"))
        self.assertEqual(result["order_id"], "123")
        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["filled_size"], 0.01)
        self.assertEqual(result["average_fill_price"], 50100.0)

    def test_reconcile_order_status_handles_missing_order(self):
        client = FakeOKXClient({"code": "0", "data": []})

        result = reconcile_order_status(client, "BTC-USDT-SWAP", "404")

        self.assertEqual(result["order_id"], "404")
        self.assertEqual(result["status"], "missing")


if __name__ == "__main__":
    unittest.main()
