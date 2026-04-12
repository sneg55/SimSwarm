"""Tests for saas.gpu.errors branches not covered by test_gpu_provider/test_runpod_hardening."""
import httpx

from saas.gpu.errors import (
    TransientGPUError,
    PermanentGPUError,
    classify_gpu_error,
)


def test_classify_transient_gpu_error_instance():
    assert classify_gpu_error(TransientGPUError("capacity")) == "transient"


def test_classify_permanent_gpu_error_instance():
    assert classify_gpu_error(PermanentGPUError("bad input")) == "permanent"


def test_classify_runtime_error_did_not_become_ready_transient():
    assert classify_gpu_error(RuntimeError("Pod did not become ready in time")) == "transient"


def test_classify_runtime_error_worker_api_at_transient():
    assert classify_gpu_error(RuntimeError("Worker API at http://x unreachable")) == "transient"


def test_classify_runtime_error_no_vastai_offers_transient():
    assert classify_gpu_error(RuntimeError("No Vast.ai offers matched")) == "transient"


def test_classify_runtime_error_all_providers_failed_transient():
    assert classify_gpu_error(RuntimeError("All GPU providers failed to provision")) == "transient"


def test_classify_generic_exception_permanent():
    assert classify_gpu_error(ValueError("something")) == "permanent"


def test_classify_read_timeout_transient():
    assert classify_gpu_error(httpx.ReadTimeout("slow")) == "transient"
