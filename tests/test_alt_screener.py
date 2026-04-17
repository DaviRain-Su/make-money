import unittest

from agent_trader.alt_screener import run_alt_screener, screen_okx_alt_swaps
from agent_trader.config import Settings
from agent_trader.models import RiskLimits


class FakeClient:
    def get_instruments(self, inst_type: str = "SWAP"):
        return {
            "data": [
                {"instId": "BTC-USDT-SWAP", "state": "live"},
                {"instId": "ETH-USDT-SWAP", "state": "live"},
                {"instId": "DOGE-USDT-SWAP", "state": "live"},
                {"instId": "ALT_BREAK-USDT-SWAP", "state": "live"},
                {"instId": "ALT_PULL-USDT-SWAP", "state": "live"},
                {"instId": "ALT_THIN-USDT-SWAP", "state": "live"},
                {"instId": "ALT_SUSP-USDT-SWAP", "state": "suspend"},
            ]
        }

    def get_tickers(self, inst_type: str = "SWAP"):
        return {
            "data": [
                {"instId": "BTC-USDT-SWAP", "last": "100", "sodUtc0": "95", "high24h": "101", "low24h": "94", "askPx": "100.2", "bidPx": "100.1", "volCcy24h": "100000000"},
                {"instId": "ETH-USDT-SWAP", "last": "100", "sodUtc0": "98", "high24h": "102", "low24h": "97", "askPx": "100.2", "bidPx": "100.1", "volCcy24h": "80000000"},
                {"instId": "DOGE-USDT-SWAP", "last": "0.2", "sodUtc0": "0.19", "high24h": "0.21", "low24h": "0.185", "askPx": "0.2002", "bidPx": "0.1999", "volCcy24h": "50000000"},
                {"instId": "ALT_BREAK-USDT-SWAP", "last": "1.49", "sodUtc0": "1.2", "high24h": "1.5", "low24h": "1.1", "askPx": "1.491", "bidPx": "1.489", "volCcy24h": "9000000"},
                {"instId": "ALT_PULL-USDT-SWAP", "last": "2.05", "sodUtc0": "1.8", "high24h": "2.2", "low24h": "1.7", "askPx": "2.052", "bidPx": "2.048", "volCcy24h": "12000000"},
                {"instId": "ALT_THIN-USDT-SWAP", "last": "0.52", "sodUtc0": "0.5", "high24h": "0.55", "low24h": "0.48", "askPx": "0.525", "bidPx": "0.515", "volCcy24h": "6000000"},
                {"instId": "ALT_SUSP-USDT-SWAP", "last": "1.3", "sodUtc0": "1.0", "high24h": "1.35", "low24h": "0.95", "askPx": "1.301", "bidPx": "1.299", "volCcy24h": "15000000"},
            ]
        }


class AltScreenerTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            environment="dev",
            okx_connector_id="okx_native",
            okx_symbol="BTC-USDT-SWAP",
            okx_api_key="k",
            okx_api_secret="s",
            okx_passphrase="p",
            okx_flag="0",
            okx_td_mode="cross",
            okx_ws_url="wss://ws.okx.com:8443/ws/v5/private",
            reconcile_poll_interval_seconds=30,
            use_okx_native=True,
            hbot_account_name="primary",
            hbot_api_url="http://localhost:8000",
            hbot_api_username="admin",
            hbot_api_password="admin",
            execution_enabled=False,
            paper_mode=True,
            proposal_risk_fraction=0.03,
            audit_log_path="var/logs/audit/events.jsonl",
            signal_shared_secret="secret",
            signal_idempotency_path="var/state/signal_ids.txt",
            control_state_path="var/state/control.json",
            admin_shared_secret="admin-secret",
            admin_nonce_path="var/state/admin_nonces.txt",
            admin_small_trade_usd=500.0,
            admin_large_trade_usd=5000.0,
            risk_limits=RiskLimits(
                max_notional_usd=1000.0,
                max_leverage=3.0,
                daily_loss_limit_pct=2.0,
                max_slippage_bps=15.0,
                min_equity_usd=25.0,
            ),
            strategy_alt_top_n=3,
            strategy_alt_min_change_pct=3.0,
            strategy_alt_min_volume_24h=5_000_000.0,
        )

    def test_screen_okx_alt_swaps_adds_category_score_and_risk_flags(self):
        results = screen_okx_alt_swaps(
            client=FakeClient(),
            top_n=3,
            min_change_pct=3.0,
            min_volume_24h=5_000_000,
            exclude_symbols=("DOGE-USDT-SWAP",),
        )

        self.assertEqual([row["instId"] for row in results], ["ALT_BREAK-USDT-SWAP", "ALT_PULL-USDT-SWAP", "ALT_THIN-USDT-SWAP"])
        self.assertEqual(results[0]["category"], "breakout")
        self.assertEqual(results[1]["category"], "pullback_watch")
        self.assertIn("high_spread", results[2]["risk_flags"])
        self.assertGreater(results[0]["score"], results[1]["score"])
        self.assertIn("distance_from_high_pct", results[0])
        self.assertIn("spread_bps", results[0])

    def test_run_alt_screener_returns_grouped_summary(self):
        result = run_alt_screener(current_settings=self.settings, client=FakeClient())

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 3)
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["category_counts"]["breakout"], 1)
        self.assertEqual(result["summary"]["category_counts"]["pullback_watch"], 1)
        self.assertEqual(result["symbols"], ["ALT_BREAK-USDT-SWAP", "ALT_PULL-USDT-SWAP", "ALT_THIN-USDT-SWAP"])


if __name__ == "__main__":
    unittest.main()
