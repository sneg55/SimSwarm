"""Tests for draft campaign endpoints."""
from unittest.mock import patch, MagicMock, AsyncMock


SEED = "A" * 600  # Minimum valid seed length


def _mock_temporal_draft():
    fake_handle = MagicMock()
    fake_handle.id = "sim-draft-id"
    fake_handle.result_run_id = "run-draft"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    return patch("saas.jobs.api_draft.get_temporal_client", new=AsyncMock(return_value=fake_client))


class TestCreateDraft:
    async def test_create_draft_with_seed(self, client, auth_headers):
        resp = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED, "enrich_web": True},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["seed_text"] == SEED
        assert data["goal"] is None
        assert data["tier"] is None
        assert data["credits_charged"] == 0

    async def test_create_draft_empty_body(self, client, auth_headers):
        resp = await client.post(
            "/api/jobs/draft",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["seed_text"] == ""

    async def test_create_draft_requires_auth(self, client):
        resp = await client.post("/api/jobs/draft", json={"seed_text": SEED})
        assert resp.status_code == 401


class TestUpdateDraft:
    async def test_update_goal(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict market impact"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["goal"] == "Predict market impact"

    async def test_update_tier(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"tier": "small"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["tier"] == "small"

    async def test_update_non_draft_returns_409(self, client, auth_headers, db_session):
        """Cannot update a job that is not in DRAFT status."""
        from saas.jobs.models import SimulationJob, JobStatus

        job = SimulationJob(
            user_id=auth_headers["_user_id"],
            seed_text=SEED,
            goal="test",
            tier="small",
            credits_charged=30,
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.patch(
            f"/api/jobs/draft/{job.id}",
            json={"goal": "new goal"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_update_other_users_draft_returns_404(self, client, auth_headers):
        resp = await client.patch(
            "/api/jobs/draft/99999",
            json={"goal": "new goal"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_seed_text_too_long(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"seed_text": "A" * 60000},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestLaunchDraft:
    async def test_launch_complete_draft(
        self, client, auth_headers, funded_user, seeded_routing
    ):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict impact", "tier": "small", "forecast_days": 30},
            headers=auth_headers,
        )

        with _mock_temporal_draft():
            resp = await client.post(
                f"/api/jobs/draft/{draft_id}/launch",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["credits_charged"] == 30

    async def test_launch_incomplete_draft_returns_422(self, client, auth_headers):
        """Draft missing goal cannot be launched."""
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_launch_insufficient_credits_returns_402(
        self, client, auth_headers, seeded_routing
    ):
        """User with 0 credits cannot launch."""
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]
        await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict impact", "tier": "small", "forecast_days": 30},
            headers=auth_headers,
        )

        resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 402

    async def test_launch_non_draft_returns_409(self, client, auth_headers, db_session):
        from saas.jobs.models import SimulationJob, JobStatus

        job = SimulationJob(
            user_id=auth_headers["_user_id"],
            seed_text=SEED,
            goal="test",
            tier="small",
            credits_charged=30,
            status=JobStatus.COMPLETED,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.post(
            f"/api/jobs/draft/{job.id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_launch_draft_rejects_null_forecast_days(
        self, client, funded_user, auth_headers, seeded_routing
    ):
        """A draft without forecast_days cannot be launched (422)."""
        draft_resp = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED, "goal": "some goal", "tier": "small"},
            headers=auth_headers,
        )
        assert draft_resp.status_code == 201
        draft_id = draft_resp.json()["id"]

        launch_resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch", headers=auth_headers,
        )
        assert launch_resp.status_code == 422
        assert "forecast_days" in launch_resp.text.lower()


class TestListIncludesDrafts:
    async def test_drafts_appear_in_job_list(self, client, auth_headers):
        await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )

        resp = await client.get("/api/jobs", headers=auth_headers)
        assert resp.status_code == 200
        jobs = resp.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["status"] == "DRAFT"


class TestDeleteDraft:
    async def test_delete_draft(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.delete(f"/api/jobs/{draft_id}", headers=auth_headers)
        assert resp.status_code == 204

        resp = await client.get(f"/api/jobs/{draft_id}", headers=auth_headers)
        assert resp.status_code == 404
