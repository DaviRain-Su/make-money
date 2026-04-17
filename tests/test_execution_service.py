import unittest

from agent_trader.execution_service import execute_trade_proposal
from agent_trader.models import TradeProposal


class FakeClient:
    def __init__(self):
        self.calls = []

    def set_leverage(self, account_name, connector_name, trading_pair, leverage):
        self.calls.append(
            ("set_leverage", account_name, connector_name, trading_pair, leverage)
        )
        return {"status": "ok", "leverage": leverage}

    def place_order(
        self,
        account_name,
        connector_name,
        trading_pair,
        trade_type,
        amount,
        order_type="MARKET",
        price=None,
        position_action="OPEN",
    ):
        self.calls.append(
            (
                "place_order",
                account_name,
                connector_name,
                trading_pair,
                trade_type,
                amount,
                order_type,
                price,
                position_action,
            )
        )
        return {"status": "submitted", "client_order_id": "abc123"}


class ExecutionServiceTests(unittest.TestCase):
    def test_paper_mode_skips_live_execution(self):
        client = FakeClient()
        proposal = TradeProposal(
            connector="okx_perpetual",
            symbol="BTC-USDT-SWAP",
            side="buy",
            notional_usd=500.0,
            leverage=2.0,
            expected_slippage_bps=5.0,
        )

        result = execute_trade_proposal(
            client=client,
            account_name="primary",
            proposal=proposal,
            execution_enabled=True,
            paper_mode=True,
            reference_price=50000.0,
        )

        self.assertEqual(result["status"], "paper")
        self.assertEqual(result["base_amount"], 0.01)
        self.assertEqual(client.calls, [])

    def test_live_execution_sets_leverage_then_places_order(self):
        client = FakeClient()
        proposal = TradeProposal(
            connector="okx_perpetual",
            symbol="BTC-USDT-SWAP",
            side="sell",
            notional_usd=600.0,
            leverage=3.0,
            expected_slippage_bps=7.0,
        )

        result = execute_trade_proposal(
            client=client,
            account_name="primary",
            proposal=proposal,
            execution_enabled=True,
            paper_mode=False,
            reference_price=30000.0,
        )

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["client_order_id"], "abc123")
        self.assertEqual(
            client.calls[0],
            ("set_leverage", "primary", "okx_perpetual", "BTC-USDT-SWAP", 3.0),
        )
        self.assertEqual(
            client.calls[1],
            (
                "place_order",
                "primary",
                "okx_perpetual",
                "BTC-USDT-SWAP",
                "SELL",
                0.02,
                "MARKET",
                None,
                "OPEN",
            ),
        )


if __name__ == "__main__":
    unittest.main()
