"""Temporal client factory. Reads TEMPORAL_ADDRESS + TEMPORAL_NAMESPACE from env."""
from __future__ import annotations

import os

from temporalio.client import Client


TEMPORAL_NAMESPACE_DEFAULT = "fishcloud"
SIM_TASK_QUEUE = "sim-queue"


async def get_temporal_client() -> Client:
    """Connect to Temporal using env config.

    Env:
      TEMPORAL_ADDRESS   — host:port, default 'temporal:7233' (docker network hostname)
      TEMPORAL_NAMESPACE — default 'fishcloud'
    """
    address = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", TEMPORAL_NAMESPACE_DEFAULT)
    return await Client.connect(address, namespace=namespace)
