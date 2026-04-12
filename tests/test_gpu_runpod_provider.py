"""Tests for saas.gpu.runpod_provider."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.gpu.provider import GPUProviderConfig
from saas.gpu.runpod_provider import RunPodProvider


def _config():
    return GPUProviderConfig(
        gpu_type="NVIDIA L40S",
        docker_image="fake/image:tag",
        max_cost_per_hour_usd=2.0,
        timeout_seconds=3600,
        env_vars={"FOO": "bar"},
    )


def test_runpod_provider_sets_api_key():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        p = RunPodProvider(api_key="k")
        assert p.api_key == "k"
        assert rp.api_key == "k"


async def test_provision_success_on_first_attempt():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod123"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "NVIDIA L40S"},
        }

        provider = RunPodProvider("key")
        inst = await provider.provision(_config())

        assert inst.instance_id == "pod123"
        assert inst.ip_address == "https://pod123-5000.proxy.runpod.net"
        assert inst.status == "running"
        # env vars should include HF_HOME
        called_env = rp.create_pod.call_args.kwargs["env"]
        assert called_env["HF_HOME"] == "/models/huggingface"
        assert called_env["FOO"] == "bar"


async def test_provision_falls_back_across_gpu_types():
    """When the primary GPU type is out of stock, provision should try the
    next GPU in the fallback list."""
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        tried = []

        def side(*a, **kw):
            tried.append(kw["gpu_type_id"])
            if len(tried) >= 3:  # succeed on 3rd attempt
                return {"id": "pod-final"}
            raise RuntimeError("no capacity")
        rp.create_pod.side_effect = side

        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }

        provider = RunPodProvider("key")
        inst = await provider.provision(_config())
        assert inst.instance_id == "pod-final"
        assert len(tried) == 3


async def test_provision_never_attaches_network_volume():
    """With the model baked into the worker image, create_pod must NEVER be
    called with network_volume_id — volume mounts would hide the baked weights
    at /models/huggingface."""
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod-baked"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }

        provider = RunPodProvider("key")
        await provider.provision(_config())

        # Inspect every call to create_pod
        for call in rp.create_pod.call_args_list:
            assert "network_volume_id" not in call.kwargs, (
                f"create_pod was called with volume kwargs: {call.kwargs}"
            )
            assert "volume_mount_path" not in call.kwargs


async def test_provision_raises_runtime_error_when_all_fail():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.side_effect = RuntimeError("capacity exhausted")

        provider = RunPodProvider("key")
        with pytest.raises(RuntimeError, match="No RunPod GPUs available"):
            await provider.provision(_config())


async def test_provision_calls_on_created_callback():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod9"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }

        cb = AsyncMock()
        provider = RunPodProvider("k")
        await provider.provision(_config(), on_created=cb)
        cb.assert_awaited_once_with("pod9")


async def test_provision_swallows_on_created_exceptions():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod9"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }

        async def bad(_):
            raise RuntimeError("cb fail")

        provider = RunPodProvider("k")
        inst = await provider.provision(_config(), on_created=bad)
        assert inst.instance_id == "pod9"


async def test_provision_times_out_when_never_ready():
    with patch("saas.gpu.runpod_provider.runpod") as rp, \
         patch("saas.gpu.runpod_provider.MAX_POLL_ATTEMPTS", 2), \
         patch("saas.gpu.runpod_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        rp.create_pod.return_value = {"id": "pod-slow"}
        rp.get_pod.return_value = {
            "desiredStatus": "PROVISIONING",
            "runtime": None,
            "machine": {"gpuDisplayName": "L40S"},
        }
        provider = RunPodProvider("k")
        with pytest.raises(TimeoutError):
            await provider.provision(_config())


async def test_provision_terminates_pod_when_readiness_times_out():
    """A pod that never becomes ready must be terminated before TimeoutError,
    otherwise it leaks GPU billing until orphan cleanup catches it."""
    with patch("saas.gpu.runpod_provider.runpod") as rp, \
         patch("saas.gpu.runpod_provider.MAX_POLL_ATTEMPTS", 2), \
         patch("saas.gpu.runpod_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        rp.create_pod.return_value = {"id": "pod-leak"}
        rp.get_pod.return_value = {
            "desiredStatus": "PROVISIONING",
            "runtime": None,
            "machine": {"gpuDisplayName": "L40S"},
        }
        provider = RunPodProvider("k")
        with pytest.raises(TimeoutError, match="did not become ready"):
            await provider.provision(_config())
        rp.terminate_pod.assert_called_once_with("pod-leak")


async def test_provision_timeout_still_raises_when_cleanup_fails():
    """If the cleanup terminate() itself fails, the readiness TimeoutError must
    still propagate — we never want to mask the root cause."""
    with patch("saas.gpu.runpod_provider.runpod") as rp, \
         patch("saas.gpu.runpod_provider.MAX_POLL_ATTEMPTS", 2), \
         patch("saas.gpu.runpod_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        rp.create_pod.return_value = {"id": "pod-leak2"}
        rp.get_pod.return_value = {
            "desiredStatus": "PROVISIONING",
            "runtime": None,
            "machine": {"gpuDisplayName": "L40S"},
        }
        rp.terminate_pod.side_effect = RuntimeError("pod not found to terminate")
        provider = RunPodProvider("k")
        with pytest.raises(TimeoutError, match="did not become ready"):
            await provider.provision(_config())


async def test_provision_handles_poll_errors_gracefully():
    """If get_status raises during polling, loop continues until timeout."""
    with patch("saas.gpu.runpod_provider.runpod") as rp, \
         patch("saas.gpu.runpod_provider.MAX_POLL_ATTEMPTS", 2), \
         patch("saas.gpu.runpod_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
        rp.create_pod.return_value = {"id": "pod-x"}
        rp.get_pod.side_effect = RuntimeError("api blip")
        provider = RunPodProvider("k")
        with pytest.raises(TimeoutError):
            await provider.provision(_config())


async def test_get_status_running():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "A100"},
        }
        provider = RunPodProvider("k")
        inst = await provider.get_status("pod-z")
        assert inst.status == "running"
        assert inst.ip_address == "https://pod-z-5000.proxy.runpod.net"
        assert inst.gpu_type == "A100"


async def test_get_status_provisioning_no_runtime():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": None,
            "machine": {"gpuDisplayName": "A100"},
        }
        provider = RunPodProvider("k")
        inst = await provider.get_status("pod-z")
        assert inst.status == "provisioning"
        assert inst.ip_address is None


async def test_get_status_missing_machine_field():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.get_pod.return_value = {"desiredStatus": None, "runtime": None}
        provider = RunPodProvider("k")
        inst = await provider.get_status("pod-z")
        assert inst.gpu_type == "unknown"


async def test_terminate_calls_runpod():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        provider = RunPodProvider("k")
        await provider.terminate("pod-kill")
        rp.terminate_pod.assert_called_once_with("pod-kill")


async def test_execute_command_returns_empty():
    with patch("saas.gpu.runpod_provider.runpod"):
        provider = RunPodProvider("k")
        out = await provider.execute_command("pod-x", "whatever")
        assert out == ""


async def test_submit_job_posts_to_worker_api():
    with patch("saas.gpu.runpod_provider.runpod"):
        provider = RunPodProvider("k")

    # Patch httpx.AsyncClient
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"status": "ok"})
    post_mock = AsyncMock(return_value=resp)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def post(self, *a, **kw):
            return await post_mock(*a, **kw)

    with patch("httpx.AsyncClient", FakeClient):
        out = await provider.submit_job("pod-abc", "seed", "goal", max_rounds=5)
        assert out == {"status": "ok"}
        post_mock.assert_awaited_once()
