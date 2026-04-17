import json
import os
import tempfile
import unittest

from agent_trader.control_state import halt_trading, read_control_state, resume_trading


class ControlStateTests(unittest.TestCase):
    def test_read_control_state_returns_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "control.json")
            state = read_control_state(path)
        self.assertFalse(state.trading_halted)
        self.assertEqual(state.halt_reason, "")
        self.assertIsNone(state.halted_at)
        self.assertIsNone(state.halted_by)

    def test_halt_trading_writes_persistent_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "control.json")
            state = halt_trading(path, reason="manual pause", actor="hermes")
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        self.assertTrue(state.trading_halted)
        self.assertEqual(raw["halt_reason"], "manual pause")
        self.assertEqual(raw["halted_by"], "hermes")
        self.assertIsNotNone(raw["halted_at"])

    def test_resume_trading_clears_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "control.json")
            halt_trading(path, reason="x", actor="hermes")
            resumed = resume_trading(path)
            persisted = read_control_state(path)
        self.assertFalse(resumed.trading_halted)
        self.assertFalse(persisted.trading_halted)
        self.assertEqual(persisted.halt_reason, "")


if __name__ == "__main__":
    unittest.main()
