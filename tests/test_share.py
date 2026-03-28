from saas.models.job import SimulationJob, JobStatus


async def _create_completed_job(db_session, user_id):
    job = SimulationJob(
        user_id=user_id, seed_text="test", goal="test goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report\nContent.", result_chat_log="[]",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


async def test_create_share_link(client, auth_headers, db_session):
    job = await _create_completed_job(db_session, auth_headers["_user_id"])
    resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert data["share_url"].startswith("/s/")


async def test_get_shared_result_no_auth(client, auth_headers, db_session):
    job = await _create_completed_job(db_session, auth_headers["_user_id"])
    # Create share link
    share_resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]
    # Access without auth
    resp = await client.get(f"/api/share/{token}")
    assert resp.status_code == 200
    assert resp.json()["goal"] == "test goal"


async def test_revoke_share_link(client, auth_headers, db_session):
    job = await _create_completed_job(db_session, auth_headers["_user_id"])
    share_resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]
    # Revoke
    await client.delete(f"/api/jobs/{job.id}/share", headers=auth_headers)
    # Should be gone
    resp = await client.get(f"/api/share/{token}")
    assert resp.status_code == 404


async def test_invalid_share_token_returns_404(client):
    resp = await client.get("/api/share/nonexistent-token")
    assert resp.status_code == 404
