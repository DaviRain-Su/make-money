import json
import os
import tempfile
import unittest

from agent_trader.market_data import (
    cache_path_for,
    fetch_historical_candles,
    load_candles_from_cache,
    load_or_fetch_candles,
    save_candles_to_cache,
)
from agent_trader.strategy import Candle


def _okx_row(ts: int, close: float) -> list:
    return [str(ts), "100", "101", "99", str(close), "1", "", "", "1"]


class FakeClient:
    def __init__(self, latest, history_pages):
        self.latest = latest
        self.history_pages = list(history_pages)  # each entry is a list of rows
        self.history_calls = []
        self.latest_calls = 0

    def get_candles(self, inst_id, bar="1H", limit="100"):
        self.latest_calls += 1
        return {"code": "0", "data": list(reversed(self.latest))}

    def get_history_candles(self, inst_id, bar="1H", after="", before="", limit="100"):
        self.history_calls.append(after)
        if not self.history_pages:
            return {"code": "0", "data": []}
        page = self.history_pages.pop(0)
        return {"code": "0", "data": list(reversed(page))}


class FetchHistoricalCandlesTests(unittest.TestCase):
    def test_single_page_latest_is_returned_sorted(self):
        latest = [_okx_row(ts, 100 + i) for i, ts in enumerate([1000, 2000, 3000])]
        client = FakeClient(latest=latest, history_pages=[])
        candles = fetch_historical_candles(client, "BTC-USDT-SWAP", target_count=3)
        self.assertEqual([c.ts for c in candles], [1000, 2000, 3000])

    def test_paginates_backward_when_more_needed(self):
        latest = [_okx_row(ts, 100) for ts in [5000, 6000, 7000]]
        older1 = [_okx_row(ts, 100) for ts in [2000, 3000, 4000]]
        older2 = [_okx_row(ts, 100) for ts in [1000]]
        client = FakeClient(latest=latest, history_pages=[older1, older2])
        candles = fetch_historical_candles(client, "BTC-USDT-SWAP", target_count=7)
        self.assertEqual([c.ts for c in candles], [1000, 2000, 3000, 4000, 5000, 6000, 7000])
        # Second history call should have been anchored on 2000
        self.assertEqual(client.history_calls[1], "2000")

    def test_stops_on_empty_history_page(self):
        latest = [_okx_row(ts, 100) for ts in [5000, 6000]]
        client = FakeClient(latest=latest, history_pages=[[]])
        candles = fetch_historical_candles(client, "BTC-USDT-SWAP", target_count=100)
        self.assertEqual(len(candles), 2)

    def test_trims_to_target_count(self):
        latest = [_okx_row(ts, 100) for ts in range(10)]
        client = FakeClient(latest=latest, history_pages=[])
        candles = fetch_historical_candles(client, "BTC-USDT-SWAP", target_count=3)
        self.assertEqual(len(candles), 3)


class CachePersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "BTC-USDT-SWAP_1H.jsonl")
            candles = [Candle(ts=i, open=1, high=2, low=0.5, close=1.5) for i in range(5)]
            save_candles_to_cache(path, candles)
            loaded = load_candles_from_cache(path)
        self.assertEqual([c.ts for c in loaded], [0, 1, 2, 3, 4])
        self.assertEqual(loaded[0].close, 1.5)

    def test_corrupt_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "x.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": 1, "open": 1, "high": 2, "low": 0, "close": 1.5}) + "\n")
                handle.write("garbage\n\n")
                handle.write(json.dumps({"ts": 2, "open": 1, "high": 2, "low": 0, "close": 2.0}) + "\n")
            loaded = load_candles_from_cache(path)
        self.assertEqual([c.ts for c in loaded], [1, 2])

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_candles_from_cache("/tmp/nonexistent.jsonl"), [])

    def test_cache_path_for_handles_slash_in_pair(self):
        p = cache_path_for("/tmp/cache", "BTC/USDT", "1H")
        self.assertEqual(p, "/tmp/cache/BTC_USDT_1H.jsonl")


class LoadOrFetchTests(unittest.TestCase):
    def test_cache_hit_skips_network(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = [Candle(ts=i * 1000, open=1, high=2, low=0.5, close=1.5) for i in range(10)]
            save_candles_to_cache(
                cache_path_for(tmpdir, "BTC-USDT-SWAP", "1H"), candles
            )
            client = FakeClient(latest=[], history_pages=[])
            result = load_or_fetch_candles(
                client=client,
                inst_id="BTC-USDT-SWAP",
                bar="1H",
                target_count=5,
                cache_dir=tmpdir,
            )
        self.assertEqual(len(result), 5)
        self.assertEqual(client.latest_calls, 0)

    def test_cache_miss_triggers_fetch_and_writes_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            latest = [_okx_row(ts, 100) for ts in [1000, 2000, 3000]]
            client = FakeClient(latest=latest, history_pages=[])
            result = load_or_fetch_candles(
                client=client,
                inst_id="BTC-USDT-SWAP",
                bar="1H",
                target_count=3,
                cache_dir=tmpdir,
            )
            self.assertEqual(len(result), 3)
            persisted = load_candles_from_cache(cache_path_for(tmpdir, "BTC-USDT-SWAP", "1H"))
        self.assertEqual([c.ts for c in persisted], [1000, 2000, 3000])


if __name__ == "__main__":
    unittest.main()
