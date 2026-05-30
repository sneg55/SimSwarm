"""Re-export all models for alembic auto-discovery."""
from saas.models.base import Base  # noqa: F401


def __getattr__(name):
    """Lazy imports to avoid circular dependencies."""
    if name in ("SimulationJob", "JobStatus", "ModelRouting", "ErrorEvent"):
        from saas.jobs import models
        return getattr(models, name)
    if name == "User":
        from saas.auth.models import User
        return User
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Base", "SimulationJob", "JobStatus", "ModelRouting", "User", "ErrorEvent"]
