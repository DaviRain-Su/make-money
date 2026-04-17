import json
import os
import tempfile
import unittest

from agent_trader.web_ui import classify_event, read_recent_audit_events, summarize_events


class WebUITests(unittest.TestCase):
    def test_read_recent_audit_events_returns_empty_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.jsonl")
            self.assertEqual(read_recent_audit_events(path), [])

    def test_read_recent_audit_events_tails_to_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                for i in range(10):
                    handle.write(json.dumps({"i": i}) + "\n")
            events = read_recent_audit_events(path, limit=3)
        self.assertEqual([e["i"] for e in events], [7, 8, 9])

    def test_read_recent_audit_events_skips_invalid_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"event_type": "ok"}) + "\n")
                handle.write("not json\n")
                handle.write("\n")
                handle.write(json.dumps({"event_type": "ok2"}) + "\n")
            events = read_recent_audit_events(path)
        self.assertEqual([e["event_type"] for e in events], ["ok", "ok2"])

    def test_classify_event_flags_blocked_and_filled(self):
        self.assertEqual(classify_event({"event_type": "risk_decision", "risk_approved": False}), "danger")
        self.assertEqual(classify_event({"event_type": "risk_decision", "risk_approved": True}), "ok")
        self.assertEqual(classify_event({"event_type": "order_submitted", "execution_status": "blocked"}), "danger")
        self.assertEqual(classify_event({"event_type": "order_submitted", "execution_status": "submitted"}), "ok")
        self.assertEqual(classify_event({"event_type": "order_reconciled", "reconciliation_status": "filled"}), "ok")
        self.assertEqual(classify_event({"event_type": "admin_action"}), "admin")
        self.assertEqual(classify_event({"event_type": "signal_processed"}), "info")

    def test_summarize_events_counts_categories(self):
        events = [
            {"event_type": "risk_decision", "risk_approved": False},
            {"event_type": "risk_decision", "risk_approved": True},
            {"event_type": "order_submitted", "execution_status": "submitted"},
            {"event_type": "order_submitted", "execution_status": "submitted"},
            {"event_type": "order_reconciled", "reconciliation_status": "filled"},
            {"event_type": "admin_action", "action": "halt"},
        ]
        counters = summarize_events(events)
        self.assertEqual(counters, {"risk_blocked": 1, "orders_submitted": 2, "orders_filled": 1, "admin_actions": 1})


if __name__ == "__main__":
    unittest.main()
