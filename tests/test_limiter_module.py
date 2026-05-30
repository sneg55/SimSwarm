"""Tests for saas.limiter helper."""
from unittest.mock import MagicMock

from saas.limiter import _get_real_client_ip, limiter


def test_real_ip_from_x_forwarded_for():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    assert _get_real_client_ip(req) == "1.2.3.4"


def test_real_ip_from_client_host():
    req = MagicMock()
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "9.9.9.9"
    assert _get_real_client_ip(req) == "9.9.9.9"


def test_real_ip_default_when_no_client():
    req = MagicMock()
    req.headers = {}
    req.client = None
    assert _get_real_client_ip(req) == "127.0.0.1"


def test_limiter_exported():
    assert limiter is not None
