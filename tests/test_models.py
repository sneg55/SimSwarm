from saas.models.job import SimulationJob, JobStatus
from saas.models.model_routing import ModelRouting


async def test_create_simulation_job(db_session):
    job = SimulationJob(
        user_id="user-123",
        seed_text="Test seed content",
        goal="Predict market sentiment",
        tier="small",
        credits_charged=30,
        status=JobStatus.PENDING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    assert job.id is not None
    assert job.user_id == "user-123"
    assert job.status == JobStatus.PENDING
    assert job.credits_charged == 30


async def test_create_model_routing(db_session):
    routing = ModelRouting(
        sim_tier="small",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="a100-40gb",
        max_rounds=200,
        vllm_args="--quantization awq",
    )
    db_session.add(routing)
    await db_session.commit()
    await db_session.refresh(routing)

    assert routing.id is not None
    assert routing.sim_tier == "small"
    assert routing.model_id == "Qwen2.5-32B-Instruct-AWQ"


async def test_job_status_transitions(db_session):
    job = SimulationJob(
        user_id="user-123",
        seed_text="Test",
        goal="Test",
        tier="small",
        credits_charged=30,
        status=JobStatus.PENDING,
    )
    db_session.add(job)
    await db_session.commit()

    job.status = JobStatus.RUNNING
    job.pipeline_stage = 1
    await db_session.commit()
    await db_session.refresh(job)

    assert job.status == JobStatus.RUNNING
    assert job.pipeline_stage == 1
