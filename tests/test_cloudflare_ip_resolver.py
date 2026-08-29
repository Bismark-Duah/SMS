import unittest
import asyncio
from unittest.mock import AsyncMock
from starlette.datastructures import Headers
from backend.app.middleware.cloudflare_guard import CloudflareGuardMiddleware, verify_turnstile_token

class DummyRequest:
    def __init__(self, headers_dict, client_host="127.0.0.1"):
        raw_headers = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers_dict.items()]
        self.headers = Headers(raw=raw_headers)
        self.state = type("State", (), {})()
        self.client = type("Client", (), {"host": client_host})()

class TestCloudflareIpResolver(unittest.TestCase):
    def test_cloudflare_connecting_ip_precedence(self):
        """Verifies that CF-Connecting-IP takes highest priority over X-Forwarded-For."""
        req = DummyRequest({
            "CF-Connecting-IP": "197.254.120.45",
            "X-Forwarded-For": "10.0.0.1, 10.0.0.2",
            "CF-IPCountry": "GH"
        })

        middleware = CloudflareGuardMiddleware(app=None)
        call_next = AsyncMock(return_value="OK")

        async def run():
            return await middleware.dispatch(req, call_next)

        res = asyncio.run(run())
        self.assertEqual(res, "OK")
        self.assertEqual(req.state.client_ip, "197.254.120.45")
        self.assertEqual(req.state.country, "GH")

    def test_x_forwarded_for_fallback(self):
        """Verifies fallback to X-Forwarded-For when CF-Connecting-IP is absent."""
        req = DummyRequest({
            "X-Forwarded-For": "154.160.10.5, 10.0.0.1"
        })

        middleware = CloudflareGuardMiddleware(app=None)
        call_next = AsyncMock(return_value="OK")

        async def run():
            return await middleware.dispatch(req, call_next)

        asyncio.run(run())
        self.assertEqual(req.state.client_ip, "154.160.10.5")

    def test_turnstile_token_validator_offline_fallback(self):
        """Verifies that Turnstile safely passes in offline development without secret keys."""
        self.assertTrue(verify_turnstile_token("any_mock_token", "127.0.0.1"))

if __name__ == "__main__":
    unittest.main()
