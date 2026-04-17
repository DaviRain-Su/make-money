import json
import os
import tempfile
import unittest

from agent_trader.reconcile_job import reconcile_open_orders_job


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_order(self, inst_id, order_id):
        self.calls.append((inst_id, order_id))
        return self.responses[(inst_id, order_id)]


class ReconcileJobTests(unittest.TestCase):
    def test_reconcile_open_orders_job_reconciles_each_order_and_logs_events(self):
        responses = {
            ("BTC-USDT-SWAP", "1"): {
                "code": "0",
                "data": [{"ordId": "1", "instId": "BTC-USDT-SWAP", "state": "filled", "fillSz": "2", "avgPx": "50010"}],
            },
            ("ETH-USDT-SWAP", "2"): {
                "code": "0",
                "data": [{"ordId": "2", "instId": "ETH-USDT-SWAP", "state": "live", "fillSz": "0", "avgPx": ""}],
            },
        }
        client = FakeClient(responses)

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "audit", "events.jsonl")
            results = reconcile_open_orders_job(
                client=client,
                open_orders=[
                    {"symbol": "BTC-USDT-SWAP", "order_id": "1"},
                    {"symbol": "ETH-USDT-SWAP", "order_id": "2"},
                ],
                audit_log_path=audit_path,
                execution_path="okx_native",
            )
            with open(audit_path, "r", encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "filled")
        self.assertEqual(results[1]["status"], "live")
        self.assertEqual(client.calls, [("BTC-USDT-SWAP", "1"), ("ETH-USDT-SWAP", "2")])
        self.assertEqual([row["event_type"] for row in rows], ["order_reconciled", "order_reconciled"])


if __name__ == "__main__":
    unittest.main()
