import unittest
from dataclasses import dataclass

from agent_trader.alerting import (
    classify_signal_result,
    push_level_alert,
    resolve_alert_urls,
)


@dataclass
class FakeSettings:
    alert_webhook_url: str = ""
    alert_webhook_info_url: str = ""
    alert_webhook_warn_url: str = ""
    alert_webhook_danger_url: str = ""
    alert_timeout_seconds: float = 5.0


class ResolveAlertUrlsTests(unittest.TestCase):
    def test_level_specific_takes_precedence_and_appends_generic(self):
        settings = FakeSettings(alert_webhook_url="http://all", alert_webhook_danger_url="http://pager")
        self.assertEqual(resolve_alert_urls(settings, "danger"), ["http://pager", "http://all"])

    def test_only_generic_falls_through_for_any_level(self):
        settings = FakeSettings(alert_webhook_url="http://all")
        self.assertEqual(resolve_alert_urls(settings, "info"), ["http://all"])
        self.assertEqual(resolve_alert_urls(settings, "warn"), ["http://all"])
        self.assertEqual(resolve_alert_urls(settings, "danger"), ["http://all"])

    def test_no_config_returns_empty(self):
        self.assertEqual(resolve_alert_urls(FakeSettings(), "danger"), [])

    def test_dedup_when_same_url_in_both_slots(self):
        settings = FakeSettings(alert_webhook_url="http://x", alert_webhook_danger_url="http://x")
        self.assertEqual(resolve_alert_urls(settings, "danger"), ["http://x"])


class PushLevelAlertTests(unittest.TestCase):
    def test_posts_to_each_matching_url(self):
        settings = FakeSettings(
            alert_webhook_url="http://all",
            alert_webhook_danger_url="http://pager",
        )
        calls = []
        def fake(url, headers, body, timeout):
            calls.append((url, body))
        results = push_level_alert(
            settings,
            event_type="signal_blocked",
            level="danger",
            payload={"symbol": "BTC-USDT-SWAP"},
            transport=fake,
        )
        self.assertEqual(len(results), 2)
        urls_called = {c[0] for c in calls}
        self.assertEqual(urls_called, {"http://pager", "http://all"})
        self.assertEqual(calls[0][1]["level"], "danger")

    def test_empty_when_no_urls(self):
        results = push_level_alert(FakeSettings(), event_type="x", level="info", payload={})
        self.assertEqual(results, [])


class ClassifyResultTests(unittest.TestCase):
    def test_blocked_is_danger(self):
        self.assertEqual(
            classify_signal_result({"risk": {"approved": False}, "execution": {"status": "blocked"}}),
            "danger",
        )

    def test_disabled_is_info(self):
        self.assertEqual(
            classify_signal_result({"risk": {"approved": True}, "execution": {"status": "disabled"}}),
            "info",
        )

    def test_normal_path_has_no_alert(self):
        self.assertIsNone(classify_signal_result({"risk": {"approved": True}, "execution": {"status": "paper"}}))


if __name__ == "__main__":
    unittest.main()
