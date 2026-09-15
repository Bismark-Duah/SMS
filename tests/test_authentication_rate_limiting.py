"""
Tests for Prompt 8: Authentication Rate Limiting
Audits the in-memory sliding-window limiter, threshold enforcement,
distinct IP isolation, proxy header resolution, window expiration, and reset behavior.
"""
import unittest
import time
from unittest.mock import MagicMock
from fastapi import HTTPException, Request

from backend.app.dependencies import (
    InMemoryRateLimiter,
    rate_limit_auth,
    auth_rate_limiter
)

class TestAuthenticationRateLimiting(unittest.TestCase):
    def setUp(self):
        auth_rate_limiter.reset()

    def tearDown(self):
        auth_rate_limiter.reset()

    def test_rate_limit_allows_under_threshold(self):
        """Requests up to max_requests (5) from an IP must succeed without error."""
        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
        client_ip = "192.168.1.100"

        for _ in range(5):
            limiter.check_rate_limit(client_ip)
        
        self.assertEqual(len(limiter.requests[client_ip]), 5)

    def test_rate_limit_blocks_exceeding_threshold(self):
        """The 6th request within window must be rejected with 429 Too Many Requests."""
        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
        client_ip = "192.168.1.101"

        for _ in range(5):
            limiter.check_rate_limit(client_ip)

        with self.assertRaises(HTTPException) as ctx:
            limiter.check_rate_limit(client_ip)

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Too many login attempts", ctx.exception.detail)
        self.assertIn("Retry-After", ctx.exception.headers)

    def test_distinct_ips_are_isolated(self):
        """Rate limiting one IP must not affect or block legitimate requests from another IP."""
        limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        ip_attacker = "192.168.1.200"
        ip_legitimate = "192.168.1.201"

        # Attacker hits limit
        for _ in range(3):
            limiter.check_rate_limit(ip_attacker)
        with self.assertRaises(HTTPException):
            limiter.check_rate_limit(ip_attacker)

        # Legitimate user can still make requests unimpeded
        for _ in range(3):
            limiter.check_rate_limit(ip_legitimate)
        self.assertEqual(len(limiter.requests[ip_legitimate]), 3)

    def test_sliding_window_expiration(self):
        """After window_seconds elapses, requests are allowed again."""
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=1)
        client_ip = "10.0.0.50"

        limiter.check_rate_limit(client_ip)
        limiter.check_rate_limit(client_ip)

        # 3rd request should fail
        with self.assertRaises(HTTPException):
            limiter.check_rate_limit(client_ip)

        # Wait for 1-second window to expire
        time.sleep(1.1)

        # Should now succeed
        limiter.check_rate_limit(client_ip)
        self.assertEqual(len(limiter.requests[client_ip]), 1)

    def test_rate_limiter_reset(self):
        """Reset clears recorded attempts and immediately restores access."""
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        client_ip = "172.16.0.10"

        limiter.check_rate_limit(client_ip)
        limiter.check_rate_limit(client_ip)

        with self.assertRaises(HTTPException):
            limiter.check_rate_limit(client_ip)

        limiter.reset(client_ip)
        self.assertEqual(len(limiter.requests[client_ip]), 0)

        # Access restored
        limiter.check_rate_limit(client_ip)
        self.assertEqual(len(limiter.requests[client_ip]), 1)

    def test_rate_limit_auth_dependency_with_proxy_headers(self):
        """rate_limit_auth extracts true client IP from X-Forwarded-For header."""
        auth_rate_limiter.reset()

        req = MagicMock(spec=Request)
        req.state = MagicMock()
        req.state.client_ip = None
        req.headers = {"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
        req.client = MagicMock(host="10.0.0.1")

        # 5 attempts under the proxy client IP
        for _ in range(5):
            rate_limit_auth(req)

        # 6th attempt should fail with 429
        with self.assertRaises(HTTPException) as ctx:
            rate_limit_auth(req)
        self.assertEqual(ctx.exception.status_code, 429)

if __name__ == "__main__":
    unittest.main()
