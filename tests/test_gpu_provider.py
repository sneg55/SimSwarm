"""Tests for GPU provider abstraction layer."""
from saas.gpu.provider import GPUProviderConfig, GPUInstance
from saas.gpu.errors import classify_gpu_error


def test_gpu_instance_creation():
    """Test that GPUInstance can be created with expected fields."""
    instance = GPUInstance(
        instance_id="inst-abc123",
        provider="runpod",
        gpu_type="RTX4090",
        ip_address="192.168.1.100",
        ssh_port=22,
        status="running",
    )
    assert instance.instance_id == "inst-abc123"
    assert instance.provider == "runpod"
    assert instance.gpu_type == "RTX4090"
    assert instance.ip_address == "192.168.1.100"
    assert instance.ssh_port == 22
    assert instance.status == "running"


def test_gpu_instance_not_ready_when_provisioning():
    """Test that is_ready returns False when status is provisioning."""
    instance = GPUInstance(
        instance_id="inst-xyz",
        provider="vastai",
        gpu_type="A100",
        ip_address=None,
        ssh_port=None,
        status="provisioning",
    )
    assert instance.is_ready is False


def test_gpu_instance_is_ready_when_running_with_ip():
    """Test that is_ready returns True when running with an IP address."""
    instance = GPUInstance(
        instance_id="inst-ready",
        provider="runpod",
        gpu_type="RTX4090",
        ip_address="10.0.0.5",
        ssh_port=22,
        status="running",
    )
    assert instance.is_ready is True


def test_gpu_provider_config_creation():
    """Test that GPUProviderConfig can be created with all fields."""
    config = GPUProviderConfig(
        gpu_type="RTX4090",
        docker_image="mirofish:latest",
        max_cost_per_hour_usd=2.50,
        timeout_seconds=3600,
        env_vars={"MY_VAR": "value"},
    )
    assert config.gpu_type == "RTX4090"
    assert config.docker_image == "mirofish:latest"
    assert config.max_cost_per_hour_usd == 2.50
    assert config.timeout_seconds == 3600
    assert config.env_vars == {"MY_VAR": "value"}


def test_gpu_provider_config_env_vars_optional():
    """Test that env_vars defaults to None."""
    config = GPUProviderConfig(
        gpu_type="A100",
        docker_image="mirofish:latest",
        max_cost_per_hour_usd=4.00,
        timeout_seconds=7200,
    )
    assert config.env_vars is None


class TestClassifyGpuError:
    def test_graph_too_small_is_permanent(self):
        exc = RuntimeError("GRAPH_TOO_SMALL: only 3 entities extracted (minimum 5)")
        assert classify_gpu_error(exc) == "permanent"

    def test_transient_patterns_still_work(self):
        exc = RuntimeError("No RunPod GPUs available for L40S")
        assert classify_gpu_error(exc) == "transient"
