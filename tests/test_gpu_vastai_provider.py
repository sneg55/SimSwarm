"""Tests for saas.gpu.vastai_provider."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.gpu.provider import GPUProviderConfig
from saas.gpu.vastai_provider import VastAIProvider


def _config(gpu_type="L40S"):
    return GPUProviderConfig(
        gpu_type=gpu_type,
        docker_image="fake/image:tag",
        max_cost_per_hour_usd=2.0,
        timeout_seconds=3600,
        env_vars={"FOO": "bar"},
    )


def _make_fake_client(responses):
    """responses: dict keyed by method name → object with .raise_for_status / .json()"""
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **kw):
            return responses["get"].pop(0) if isinstance(responses.get("get"), list) else responses["get"]

        async def put(self, *a, **kw):
            return responses["put"]

        async def delete(self, *a, **kw):
            return responses.get("delete", MagicMock())
    return FakeClient


def _resp(payload, status=200):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    r.status_code = status
    return r


async def test_provision_success():
    search_resp = _resp({"offers": [{"id": 111}]})
    create_resp = _resp({"new_contract": 777})
    status_resp = _resp({
        "instances": {
            "actual_status": "running",
            "gpu_name": "L40S",
            "public_ipaddr": "1.2.3.4",
            "ssh_port": 2222,
        }
    })

    FakeClient = _make_fake_client({"get": [search_resp, status_resp], "put": create_resp})
    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient), \
         patch("saas.gpu.vastai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        provider = VastAIProvider("api")
        inst = await provider.provision(_config())
        assert inst.instance_id == "777"
        assert inst.ip_address == "1.2.3.4"
        assert inst.is_ready


async def test_provision_maps_a100_80gb_name():
    search_resp = _resp({"offers": [{"id": 1}]})
    create_resp = _resp({"new_contract": 2})
    status_resp = _resp({
        "instances": {"actual_status": "running", "public_ipaddr": "1.1.1.1", "gpu_name": "A100_PCIE"}
    })
    captured = {}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def get(self, url, params=None):
            if "bundles" in url:
                captured["q"] = params["q"]
                return search_resp
            return status_resp
        async def put(self, *a, **kw):
            return create_resp

    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient), \
         patch("saas.gpu.vastai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        provider = VastAIProvider("api")
        await provider.provision(_config(gpu_type="A100 80GB"))

    assert "A100_PCIE" in captured["q"]


async def test_provision_maps_h100():
    search_resp = _resp({"offers": [{"id": 1}]})
    create_resp = _resp({"new_contract": 2})
    status_resp = _resp({
        "instances": {"actual_status": "running", "public_ipaddr": "1.1.1.1", "gpu_name": "H100_SXM"}
    })
    captured = {}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def get(self, url, params=None):
            if "bundles" in url:
                captured["q"] = params["q"]
                return search_resp
            return status_resp
        async def put(self, *a, **kw):
            return create_resp

    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient), \
         patch("saas.gpu.vastai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        provider = VastAIProvider("api")
        await provider.provision(_config(gpu_type="H100 PCIE"))
    assert "H100_SXM" in captured["q"]


async def test_provision_no_offers_raises():
    search_resp = _resp({"offers": []})
    FakeClient = _make_fake_client({"get": [search_resp], "put": _resp({})})
    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient):
        provider = VastAIProvider("api")
        with pytest.raises(RuntimeError, match="No Vast.ai offers"):
            await provider.provision(_config())


async def test_provision_invokes_on_created():
    search_resp = _resp({"offers": [{"id": 1}]})
    create_resp = _resp({"new_contract": 42})
    status_resp = _resp({
        "instances": {"actual_status": "running", "public_ipaddr": "9.9.9.9", "gpu_name": "L40S"}
    })
    FakeClient = _make_fake_client({"get": [search_resp, status_resp], "put": create_resp})

    cb = AsyncMock()
    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient), \
         patch("saas.gpu.vastai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        provider = VastAIProvider("api")
        await provider.provision(_config(), on_created=cb)
    cb.assert_awaited_once_with("42")


async def test_provision_times_out_when_never_ready():
    search_resp = _resp({"offers": [{"id": 1}]})
    create_resp = _resp({"new_contract": 55})
    provisioning_resp = _resp({
        "instances": {"actual_status": "provisioning", "public_ipaddr": None, "gpu_name": "L40S"}
    })

    # Return provisioning_resp on every GET after the first (search) call.
    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        calls = {"get": 0}
        async def get(self, *a, **kw):
            self.__class__.calls["get"] += 1
            if self.__class__.calls["get"] == 1:
                return search_resp
            return provisioning_resp
        async def put(self, *a, **kw):
            return create_resp

    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient), \
         patch("saas.gpu.vastai_provider.MAX_POLL_ATTEMPTS", 2), \
         patch("saas.gpu.vastai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        provider = VastAIProvider("api")
        with pytest.raises(TimeoutError):
            await provider.provision(_config())


async def test_get_status_provisioning():
    resp = _resp({"instances": {"actual_status": "loading", "public_ipaddr": None, "gpu_name": "L40S"}})

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def get(self, *a, **kw):
            return resp

    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient):
        provider = VastAIProvider("api")
        inst = await provider.get_status("42")
        assert inst.status == "provisioning"


async def test_terminate_calls_delete():
    called = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def delete(self, *a, **kw):
            called["n"] += 1
            return _resp({})

    with patch("saas.gpu.vastai_provider.httpx.AsyncClient", FakeClient):
        provider = VastAIProvider("api")
        await provider.terminate("42")
    assert called["n"] == 1


async def test_execute_command_returns_empty():
    provider = VastAIProvider("api")
    out = await provider.execute_command("42", "echo")
    assert out == ""
