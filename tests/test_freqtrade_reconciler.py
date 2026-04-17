import unittest

from agent_trader.freqtrade_reconciler import force_exit_trade


class ForceExitTradeTests(unittest.TestCase):
    def test_posts_to_forceexit_with_basic_auth(self):
        captured = {}
        def fake(method, url, headers, body):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return {"result": "ok"}
        result = force_exit_trade(
            api_url="http://freqtrade.local:8080",
            username="u",
            password="p",
            trade_id=42,
            transport=fake,
        )
        self.assertEqual(result, {"result": "ok"})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "http://freqtrade.local:8080/api/v1/forceexit")
        self.assertTrue(captured["headers"]["Authorization"].startswith("Basic "))
        self.assertEqual(captured["body"], {"tradeid": 42})

    def test_strips_trailing_slash_in_api_url(self):
        captured = {}
        def fake(_m, url, _h, _b):
            captured["url"] = url
            return {}
        force_exit_trade(
            api_url="http://freqtrade.local:8080/",
            username="u",
            password="p",
            trade_id=1,
            transport=fake,
        )
        self.assertEqual(captured["url"], "http://freqtrade.local:8080/api/v1/forceexit")

    def test_blank_api_url_raises(self):
        with self.assertRaises(ValueError):
            force_exit_trade(api_url="", username="u", password="p", trade_id=1, transport=lambda *_: {})

    def test_blank_trade_id_raises(self):
        with self.assertRaises(ValueError):
            force_exit_trade(api_url="http://x", username="u", password="p", trade_id=None, transport=lambda *_: {})


if __name__ == "__main__":
    unittest.main()
