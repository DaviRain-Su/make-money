import unittest

from agent_trader.alt_screener import screen_okx_alt_swaps


class FakeClient:
    def get_instruments(self, inst_type: str = "SWAP"):
        return {
            "data": [
                {"instId": "BTC-USDT-SWAP", "state": "live"},
                {"instId": "ETH-USDT-SWAP", "state": "live"},
                {"instId": "DOGE-USDT-SWAP", "state": "live"},
                {"instId": "ALT1-USDT-SWAP", "state": "live"},
                {"instId": "ALT2-USDT-SWAP", "state": "live"},
                {"instId": "ALT3-USDT-SWAP", "state": "suspend"},
            ]
        }

    def get_tickers(self, inst_type: str = "SWAP"):
        return {
            "data": [
                {"instId": "BTC-USDT-SWAP", "last": "100", "sodUtc0": "95", "volCcy24h": "100000000"},
                {"instId": "ETH-USDT-SWAP", "last": "100", "sodUtc0": "98", "volCcy24h": "80000000"},
                {"instId": "DOGE-USDT-SWAP", "last": "0.2", "sodUtc0": "0.19", "volCcy24h": "50000000"},
                {"instId": "ALT1-USDT-SWAP", "last": "1.5", "sodUtc0": "1.0", "volCcy24h": "9000000"},
                {"instId": "ALT2-USDT-SWAP", "last": "2.0", "sodUtc0": "1.9", "volCcy24h": "12000000"},
                {"instId": "ALT3-USDT-SWAP", "last": "1.3", "sodUtc0": "1.0", "volCcy24h": "15000000"},
            ]
        }


class AltScreenerTests(unittest.TestCase):
    def test_screen_okx_alt_swaps_filters_majors_and_ranks_candidates(self):
        results = screen_okx_alt_swaps(
            client=FakeClient(),
            top_n=2,
            min_change_pct=3.0,
            min_volume_24h=5_000_000,
            exclude_symbols=("DOGE-USDT-SWAP",),
        )

        self.assertEqual([row["instId"] for row in results], ["ALT1-USDT-SWAP", "ALT2-USDT-SWAP"])
        self.assertGreater(results[0]["change_pct_24h"], results[1]["change_pct_24h"])
        self.assertEqual(results[0]["volume_24h_quote"], 9000000.0)


if __name__ == "__main__":
    unittest.main()
