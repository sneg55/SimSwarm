"""Tests for saas.jobs.fetch URL fetcher (SSRF + HTML parser)."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from saas.jobs.fetch import _html_to_text, _is_private_ip, _validate_url
from fastapi import HTTPException


def test_html_to_text_strips_tags():
    html = "<html><body><p>Hello <b>World</b></p></body></html>"
    assert _html_to_text(html) == "Hello World"


def test_html_to_text_removes_scripts_and_styles():
    html = "<style>body{}</style><script>bad()</script><p>OK</p>"
    text = _html_to_text(html)
    assert "bad()" not in text
    assert "body{}" not in text
    assert "OK" in text


def test_html_to_text_decodes_entities():
    html = "<p>AT&amp;T &lt;foo&gt; &quot;hi&quot; &#39;bye&#39;</p>"
    assert _html_to_text(html) == "AT&T <foo> \"hi\" 'bye'"


def test_is_private_ip_rejects_loopback():
    assert _is_private_ip("127.0.0.1") is True


def test_is_private_ip_rejects_internal_10_net():
    assert _is_private_ip("10.0.0.1") is True


def test_is_private_ip_invalid_hostname_returns_false():
    # A non-resolving host returns False after gaierror
    assert _is_private_ip("nonexistent-host-xyz-abc-123.invalid") is False


def test_validate_url_rejects_non_http():
    with pytest.raises(HTTPException) as exc:
        _validate_url("ftp://example.com/file")
    assert exc.value.status_code == 400


def test_validate_url_rejects_missing_host():
    with pytest.raises(HTTPException):
        _validate_url("http://")


def test_validate_url_rejects_blocked_hosts():
    with pytest.raises(HTTPException):
        _validate_url("http://169.254.169.254/latest/meta-data/")


def test_validate_url_rejects_private_ip():
    with pytest.raises(HTTPException):
        _validate_url("http://10.0.0.1/")


async def test_fetch_unauthenticated(client):
    resp = await client.post("/api/fetch", json={"url": "http://example.com"})
    assert resp.status_code == 401


async def test_fetch_rejects_blocked_url(client, auth_headers):
    resp = await client.post(
        "/api/fetch",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def _mock_ctx(mock_client):
    mc = AsyncMock()
    mc.__aenter__.return_value = mock_client
    mc.__aexit__.return_value = False
    return mc


async def test_fetch_success_html(client, auth_headers):
    resp_obj = MagicMock()
    resp_obj.content = b"<html><body><p>Hello from the page</p></body></html>"
    resp_obj.text = "<html><body><p>Hello from the page</p></body></html>"
    resp_obj.headers = {"content-type": "text/html; charset=utf-8"}
    resp_obj.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = resp_obj

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch",
            json={"url": "http://example.com/page"},
            headers=auth_headers,
        )
    assert r.status_code == 200
    data = r.json()
    assert "Hello from the page" in data["text"]


async def test_fetch_success_json_content(client, auth_headers):
    body_str = '{"data": "hello world"}'
    resp_obj = MagicMock()
    resp_obj.content = body_str.encode()
    resp_obj.text = body_str
    resp_obj.headers = {"content-type": "application/json"}
    resp_obj.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = resp_obj

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch",
            json={"url": "http://example.com/api"},
            headers=auth_headers,
        )
    assert r.status_code == 200
    assert "hello world" in r.json()["text"]


async def test_fetch_plain_text(client, auth_headers):
    body_str = "Just plain text content here"
    resp_obj = MagicMock()
    resp_obj.content = body_str.encode()
    resp_obj.text = body_str
    resp_obj.headers = {"content-type": "text/plain"}
    resp_obj.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = resp_obj

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch",
            json={"url": "http://example.com/plain"},
            headers=auth_headers,
        )
    assert r.status_code == 200


async def test_fetch_content_too_large(client, auth_headers):
    resp_obj = MagicMock()
    resp_obj.content = b"x" * 6_000_000
    resp_obj.text = "x" * 100
    resp_obj.headers = {"content-type": "text/html"}
    resp_obj.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = resp_obj

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch",
            json={"url": "http://example.com/big"},
            headers=auth_headers,
        )
    assert r.status_code == 400
    assert "too large" in r.json()["detail"].lower()


async def test_fetch_http_status_error(client, auth_headers):
    err_resp = MagicMock()
    err_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("fail", request=MagicMock(), response=err_resp)

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch", json={"url": "http://example.com/bad"}, headers=auth_headers,
        )
    assert r.status_code == 400
    assert "500" in r.json()["detail"]


async def test_fetch_timeout(client, auth_headers):
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("slow")

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch", json={"url": "http://example.com/slow"}, headers=auth_headers,
        )
    assert r.status_code == 400
    assert "timed out" in r.json()["detail"].lower()


async def test_fetch_connection_error(client, auth_headers):
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("unreachable")

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch", json={"url": "http://example.com/gone"}, headers=auth_headers,
        )
    assert r.status_code == 400
    assert "Could not reach" in r.json()["detail"]


async def test_fetch_empty_text(client, auth_headers):
    resp_obj = MagicMock()
    resp_obj.content = b"   "
    resp_obj.text = "   "
    resp_obj.headers = {"content-type": "text/html"}
    resp_obj.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = resp_obj

    with patch("saas.jobs.fetch.httpx.AsyncClient", return_value=_mock_ctx(mock_client)):
        r = await client.post(
            "/api/fetch", json={"url": "http://example.com/empty"}, headers=auth_headers,
        )
    assert r.status_code == 400
