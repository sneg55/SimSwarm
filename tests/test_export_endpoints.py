import pytest


@pytest.mark.asyncio
async def test_export_pdf_returns_pdf(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        status=JobStatus.COMPLETED,
        result_report="# Test Report\n\nSome content here.",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_export_json_returns_json(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test",
        goal="test goal",
        tier="small",
        credits_charged=30,
        status=JobStatus.COMPLETED,
        result_report="# Report",
        result_chat_log="[]",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/json", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal"] == "test goal"
    assert data["report"] == "# Report"


@pytest.mark.asyncio
async def test_export_json_forbidden_for_other_user(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    job = SimulationJob(
        user_id="other-user-id",
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        status=JobStatus.COMPLETED,
        result_report="# Report",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/json", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_json_no_results(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        status=JobStatus.RUNNING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/json", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_json_includes_structured_and_enrichment(client, auth_headers, db_session):
    """Export JSON should surface structured, enriched_seed, enrichment_citations, key_insight."""
    from saas.jobs.models import SimulationJob, JobStatus
    import json

    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="s", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Done", result_chat_log="[]", result_graph="{}",
        result_structured='{"brief": "b", "findings": []}',
        enriched_seed="background facts",
        enrichment_citations='[{"url": "https://x.test", "title": "Src"}]',
        key_insight="headline finding",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/json", headers=auth_headers)
    assert resp.status_code == 200
    body = json.loads(resp.content)
    assert body["structured"] == {"brief": "b", "findings": []}
    assert body["enriched_seed"] == "background facts"
    assert body["enrichment_citations"] == [{"url": "https://x.test", "title": "Src"}]
    assert body["key_insight"] == "headline finding"
