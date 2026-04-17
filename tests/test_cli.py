import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agent_trader.cli import main


class CLITests(unittest.TestCase):
    def test_demo_smoke_command_prints_json_summary(self):
        payload = {
            "side": "buy",
            "confidence": 0.8,
            "entry_price": 50000,
            "stop_loss_price": 49000,
            "take_profit_price": 52000,
            "expected_slippage_bps": 5,
            "leverage": 2,
            "rationale": "cli smoke",
            "client_signal_id": "cli-001",
        }
        with patch("agent_trader.cli.run_demo_smoke_test", return_value={"summary": {"order_id": "123"}}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main(["demo-smoke", json.dumps(payload)])

        self.assertEqual(exit_code, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["summary"]["order_id"], "123")

    def test_runtime_once_command_runs_daemon_once(self):
        fake_daemon = type("FakeDaemon", (), {"run_once": lambda self, send_ping=False: None})()
        with patch("agent_trader.cli.build_runtime_daemon", return_value=fake_daemon):
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main(["runtime-once"])

        self.assertEqual(exit_code, 0)
        self.assertIn("runtime-once complete", buf.getvalue())

    def test_invalid_command_returns_nonzero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = main(["unknown-cmd"])
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
