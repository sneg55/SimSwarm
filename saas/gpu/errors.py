"""GPU error classification for retry decisions."""
import httpx


class TransientGPUError(Exception):
    """Retryable infrastructure error (timeout, network, capacity)."""
    pass


class PermanentGPUError(Exception):
    """Non-retryable error (bad input, pipeline logic failure, OOM)."""
    pass


_TRANSIENT_PATTERNS = [
    "No RunPod GPUs available",
    "All GPU providers failed",
    "did not become ready",
    "Worker API at",
]


def classify_gpu_error(exc: Exception) -> str:
    """Return 'transient' or 'permanent' for a GPU job error."""
    if isinstance(exc, (TimeoutError, httpx.ConnectError, httpx.ReadTimeout)):
        return "transient"
    if isinstance(exc, TransientGPUError):
        return "transient"
    if isinstance(exc, PermanentGPUError):
        return "permanent"
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        for pattern in _TRANSIENT_PATTERNS:
            if pattern in msg:
                return "transient"
        return "permanent"
    return "permanent"
