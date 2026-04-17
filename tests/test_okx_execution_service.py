import unittest

from agent_trader.models import TradeProposal
from agent_trader.okx_execution_service import execute_okx_trade_proposal


class FakeOKXClient:
    def __init__(self):
        self.calls = []

    def get_contract_value(self, inst_id):
        self.calls.append({"contract_value": inst_id})
        return 0.01

    def place_market_order(self, inst_id, side, size, leverage, reduce_only, pos_side='', attach_algo_ords=None):
        self.calls.append(
            {
                "inst_id": inst_id,
                "side": side,
                "size": size,
                "leverage": leverage,
                "reduce_only": reduce_only,
                "pos_side": pos_side,
                "attach_algo_ords": attach_algo_ords,
            }
        )
        return {"code": "0", "data": [{"ordId": "999"}]}

    def get_order(self, inst_id, order_id):
        self.calls.append({"reconcile": (inst_id, order_id)})
        return {
            "code": "0",
            "data": [
                {
                    "ordId": order_id,
                    "state": "filled",
                    "fillSz": "2",
                    "avgPx": "30010",
                    "instId": inst_id,
                    "side": "sell",
                }
            ],
        }


class OKXExecutionServiceTests(unittest.TestCase):
    def test_paper_mode_skips_live_order_and_exposes_attached_algo(self):
        client = FakeOKXClient()
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="buy",
            notional_usd=500.0,
            leverage=2.0,
            expected_slippage_bps=5.0,
            stop_loss_price=49000.0,
            take_profit_price=52000.0,
        )
        result = execute_okx_trade_proposal(
            client=client,
            proposal=proposal,
            execution_enabled=True,
            paper_mode=True,
            reference_price=50000.0,
        )
        self.assertEqual(result["status"], "paper")
        self.assertEqual(result["size"], "1")
        self.assertEqual(result["attach_algo_ords"][0]["slTriggerPx"], "49000.0")
        self.assertEqual(client.calls, [{"contract_value": "BTC-USDT-SWAP"}])

    def test_live_mode_places_market_order_and_reconciles_status(self):
        client = FakeOKXClient()
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="sell",
            notional_usd=600.0,
            leverage=3.0,
            expected_slippage_bps=5.0,
            stop_loss_price=30500.0,
            take_profit_price=28500.0,
        )
        result = execute_okx_trade_proposal(
            client=client,
            proposal=proposal,
            execution_enabled=True,
            paper_mode=False,
            reference_price=30000.0,
        )
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["order_id"], "999")
        self.assertEqual(result["reconciliation"]["status"], "filled")
        self.assertEqual(result["reconciliation"]["filled_size"], 2.0)
        self.assertEqual(
            client.calls[1],
            {
                "inst_id": "BTC-USDT-SWAP",
                "side": "sell",
                "size": "2",
                "leverage": 3.0,
                "reduce_only": False,
                "pos_side": "",
                "attach_algo_ords": [{"tpTriggerPx": "28500.0", "tpOrdPx": "-1", "slTriggerPx": "30500.0", "slOrdPx": "-1"}],
            },
        )
        self.assertEqual(client.calls[2], {"reconcile": ("BTC-USDT-SWAP", "999")})

    def test_close_position_uses_reduce_only_and_no_attached_algo(self):
        client = FakeOKXClient()
        proposal = TradeProposal(
            connector="okx_native",
            symbol="BTC-USDT-SWAP",
            side="sell",
            notional_usd=600.0,
            leverage=3.0,
            expected_slippage_bps=5.0,
            position_action="CLOSE",
            stop_loss_price=30500.0,
            take_profit_price=28500.0,
        )
        result = execute_okx_trade_proposal(
            client=client,
            proposal=proposal,
            execution_enabled=True,
            paper_mode=False,
            reference_price=30000.0,
        )
        self.assertEqual(result["position_action"], "CLOSE")
        self.assertTrue(client.calls[1]["reduce_only"])
        self.assertIsNone(client.calls[1]["attach_algo_ords"])


if __name__ == "__main__":
    unittest.main()
