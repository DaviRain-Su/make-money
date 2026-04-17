import unittest

from agent_trader.alerting import classify_signal_result, push_alert


class PushAlertTests(unittest.TestCase):
    def test_skipped_when_webhook_url_missing(self):
        result = push_alert(webhook_url="", event_type="x", level="danger", payload={})
        self.assertEqual(result["status"], "skipped")

    def test_posts_json_body_with_level_and_event(self):
        captured = {}
        def fake(url, headers, body, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            captured["timeout"] = timeout
        result = push_alert(
            webhook_url="http://alert.local/webhook",
            event_type="signal_blocked",
            level="danger",
            payload={"symbol": "BTC-USDT-SWAP", "risk_reasons": ["halt"]},
            transport=fake,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["url"], "http://alert.local/webhook")
        self.assertEqual(captured["headers"]["Content-Type"], "application/json")
        self.assertEqual(captured["body"]["event_type"], "signal_blocked")
        self.assertEqual(captured["body"]["level"], "danger")
        self.assertEqual(captured["body"]["symbol"], "BTC-USDT-SWAP")

    def test_transport_failure_is_captured_in_result(self):
        def boom(*_a, **_kw):
            raise RuntimeError("network down")
        result = push_alert(
            webhook_url="http://x",
            event_type="halt",
            level="danger",
            payload={},
            transport=boom,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("network down", result["error"])


class ClassifySignalResultTests(unittest.TestCase):
    def test_blocked_execution_is_danger(self):
        self.assertEqual(
            classify_signal_result({"risk": {"approved": False}, "execution": {"status": "blocked"}}),
            "danger",
        )

    def test_risk_rejection_is_danger(self):
        self.assertEqual(
            classify_signal_result({"risk": {"approved": False}, "execution": {"status": "disabled"}}),
            "danger",
        )

    def test_normal_execution_is_ignored(self):
        self.assertIsNone(classify_signal_result({"risk": {"approved": True}, "execution": {"status": "paper"}}))


if __name__ == "__main__":
    unittest.main()
