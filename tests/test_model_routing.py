"""Tests for ModelRouting table queries."""
import pytest
from sqlalchemy import select

from saas.jobs.models import ModelRouting
from saas.gpu.provider import GPUProviderConfig


def _seed_defaults(session_sync):
    """Helper to insert default routing entries (would normally be a migration)."""
    defaults = [
        ModelRouting(
            sim_tier="small",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=25,
            target_agents=10,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
        ModelRouting(
            sim_tier="medium",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=100,
            target_agents=20,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
        ModelRouting(
            sim_tier="large",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=200,
            target_agents=35,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
    ]
    for row in defaults:
        session_sync.add(row)


@pytest.mark.asyncio
async def test_seed_default_routing_entries(db_session):
    """Seeding inserts three tier rows (small, medium, large)."""
    _seed_defaults(db_session)
    await db_session.commit()

    result = await db_session.execute(select(ModelRouting))
    rows = result.scalars().all()
    tiers = {r.sim_tier for r in rows}
    assert tiers == {"small", "medium", "large"}


@pytest.mark.asyncio
async def test_get_routing_for_tier(db_session):
    """Query for a specific tier returns the correct model_id and gpu_type."""
    _seed_defaults(db_session)
    await db_session.commit()

    stmt = select(ModelRouting).where(ModelRouting.sim_tier == "medium")
    result = await db_session.execute(stmt)
    row = result.scalar_one()

    assert row.model_id == "Qwen/Qwen3-14B"
    assert row.gpu_type == "NVIDIA L40S"
    assert row.max_rounds == 100


@pytest.mark.asyncio
async def test_routing_to_gpu_config(db_session):
    """A ModelRouting row can be converted to a GPUProviderConfig."""
    _seed_defaults(db_session)
    await db_session.commit()

    stmt = select(ModelRouting).where(ModelRouting.sim_tier == "large")
    result = await db_session.execute(stmt)
    row = result.scalar_one()

    gpu_config = GPUProviderConfig(
        gpu_type=row.gpu_type,
        docker_image="mirofish:latest",
        max_cost_per_hour_usd=4.00,
        timeout_seconds=43200,
    )

    assert gpu_config.gpu_type == "NVIDIA L40S"
    assert gpu_config.timeout_seconds == 43200
