import json
import os
import tempfile
import unittest

from agent_trader.audit_log import append_audit_event


class AuditLogTests(unittest.TestCase):
    def test_append_audit_event_writes_json_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "audit", "events.jsonl")
            append_audit_event(
                path,
                {
                    "event_type": "signal_processed",
                    "symbol": "BTC-USDT-SWAP",
                    "status": "paper",
                },
            )

            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()

        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["event_type"], "signal_processed")
        self.assertEqual(payload["symbol"], "BTC-USDT-SWAP")
        self.assertIn("timestamp", payload)


if __name__ == "__main__":
    unittest.main()
