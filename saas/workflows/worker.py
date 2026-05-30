"""Temporal worker bootstrap. Run as: python -m saas.workflows.worker"""
from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from saas.workflows.activities.finalization import (
    mark_failed, upload_and_finalize,
)
from saas.workflows.activities.pipeline import submit_and_poll
from saas.workflows.activities.pre_gpu import derive_markets, enrich_seed
from saas.workflows.activities.provisioning import (
    clear_pod_id, provision_pod, terminate_pod, wait_for_worker_health,
)
from saas.workflows.client import SIM_TASK_QUEUE, get_temporal_client
from saas.workflows.sim_workflow import SimulationWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("saas.workflows.worker")


async def main() -> None:
    client = await get_temporal_client()
    logger.info("temporal.worker.connected task_queue=%s", SIM_TASK_QUEUE)

    worker = Worker(
        client,
        task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow],
        activities=[
            enrich_seed, derive_markets,
            provision_pod, wait_for_worker_health, terminate_pod, clear_pod_id,
            submit_and_poll,
            upload_and_finalize, mark_failed,
        ],
    )
    logger.info("temporal.worker.starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
