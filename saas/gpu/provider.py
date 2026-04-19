from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GPUProviderConfig:
    gpu_type: str
    docker_image: str
    max_cost_per_hour_usd: float
    timeout_seconds: int
    env_vars: dict[str, str] | None = None
    # When set, the provider tags the pod with the job_id so cleanup can
    # confirm the binding even if the DB's simulation_jobs.pod_id drifts.
    job_id: int | None = None


@dataclass
class GPUInstance:
    instance_id: str
    provider: str
    gpu_type: str
    ip_address: str | None
    ssh_port: int | None
    status: str  # provisioning, running, stopped, error

    @property
    def is_ready(self) -> bool:
        return self.status == "running" and self.ip_address is not None


class GPUProvider(ABC):
    @abstractmethod
    async def provision(self, config: GPUProviderConfig, on_created=None) -> GPUInstance: ...

    @abstractmethod
    async def get_status(self, instance_id: str) -> GPUInstance: ...

    @abstractmethod
    async def terminate(self, instance_id: str) -> None: ...

    @abstractmethod
    async def execute_command(self, instance_id: str, command: str) -> str: ...
