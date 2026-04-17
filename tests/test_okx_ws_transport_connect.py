import unittest
from unittest.mock import patch

from agent_trader.okx_ws_transport import connect_with_websockets


class ConnectWithWebsocketsTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_with_websockets_uses_library_connect(self):
        sentinel = object()

        async def fake_connect(url):
            self.assertEqual(url, "wss://example")
            return sentinel

        with patch("agent_trader.okx_ws_transport._import_websockets_connect", return_value=fake_connect):
            result = await connect_with_websockets("wss://example")

        self.assertIs(result, sentinel)


if __name__ == "__main__":
    unittest.main()
