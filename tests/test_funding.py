import unittest

from agent_trader.funding import FundingGuard, FundingSnapshot, parse_funding_rate_response


class ParseFundingRateTests(unittest.TestCase):
    def test_parses_rate_and_next_time(self):
        snap = parse_funding_rate_response({
            "data": [
                {"instId": "BTC-USDT-SWAP", "fundingRate": "0.0002", "nextFundingTime": "1700000000000"},
            ]
        })
        self.assertIsNotNone(snap)
        self.assertEqual(snap.symbol, "BTC-USDT-SWAP")
        self.assertAlmostEqual(snap.funding_rate, 0.0002)
        self.assertEqual(snap.next_funding_time_ms, 1700000000000)

    def test_returns_none_for_empty_payload(self):
        self.assertIsNone(parse_funding_rate_response({"data": []}))
        self.assertIsNone(parse_funding_rate_response({}))

    def test_rejects_non_numeric_rate(self):
        self.assertIsNone(parse_funding_rate_response({"data": [{"fundingRate": "nope"}]}))


class FundingGuardDisabledTests(unittest.TestCase):
    def test_disabled_guard_always_allows(self):
        guard = FundingGuard(client=None, max_abs_bps=0)
        self.assertFalse(guard.is_enabled())
        self.assertEqual(guard.check("BTC-USDT-SWAP", "buy")["allowed"], True)


class FakeClientFixed:
    def __init__(self, rate):
        self.rate = rate
        self.calls = 0

    def get_funding_rate(self, inst_id):
        self.calls += 1
        return {"data": [{"instId": inst_id, "fundingRate": str(self.rate), "nextFundingTime": "1700000000000"}]}


class FundingGuardCheckTests(unittest.TestCase):
    def test_within_threshold_allows(self):
        guard = FundingGuard(client=FakeClientFixed(0.0001), max_abs_bps=5.0)  # 1 bps
        result = guard.check("BTC-USDT-SWAP", "buy")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "within_threshold")

    def test_blocks_long_when_funding_too_positive(self):
        guard = FundingGuard(client=FakeClientFixed(0.001), max_abs_bps=5.0)  # 10 bps
        result = guard.check("BTC-USDT-SWAP", "buy")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "funding_cost_long")
        self.assertAlmostEqual(result["funding_bps"], 10.0)

    def test_blocks_short_when_funding_too_negative(self):
        guard = FundingGuard(client=FakeClientFixed(-0.001), max_abs_bps=5.0)
        result = guard.check("BTC-USDT-SWAP", "sell")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "funding_cost_short")

    def test_allows_when_beyond_threshold_but_in_favor(self):
        # funding very positive (shorts paying longs); taking a short pays us
        guard = FundingGuard(client=FakeClientFixed(0.001), max_abs_bps=5.0)
        result = guard.check("BTC-USDT-SWAP", "sell")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "beyond_threshold_in_favor")

    def test_caches_within_ttl(self):
        fake = FakeClientFixed(0.0001)
        guard = FundingGuard(client=fake, max_abs_bps=5.0, ttl_seconds=300)
        guard.check("BTC-USDT-SWAP", "buy")
        guard.check("BTC-USDT-SWAP", "buy")
        guard.check("BTC-USDT-SWAP", "sell")
        self.assertEqual(fake.calls, 1)  # cached

    def test_snapshot_unavailable_fails_open(self):
        class BrokenClient:
            def get_funding_rate(self, _inst):
                raise RuntimeError("network down")
        guard = FundingGuard(client=BrokenClient(), max_abs_bps=5.0)
        result = guard.check("BTC-USDT-SWAP", "buy")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "snapshot_unavailable")


if __name__ == "__main__":
    unittest.main()
