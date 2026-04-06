"""Tests for the GET /api/jobs/{job_id}/graph endpoint."""
from __future__ import annotations

import json

from sqlalchemy import text

from saas.jobs.models import SimulationJob, JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_GRAPH_JSON = json.dumps({
    "nodes": [
        {
            "uuid": "n1",
            "name": "Alice",
            "labels": ["Person"],
            "summary": "A test node",
            "connection_count": 1,
        },
    ],
    "edges": [
        {
            "uuid": "e1",
            "name": "knows",
            "fact": "Alice knows Bob",
            "source_node_uuid": "n1",
            "target_node_uuid": "n2",
            "source_node_name": "Alice",
            "target_node_name": "Bob",
        },
    ],
    "metadata": {
        "entity_types": ["Person"],
        "total_nodes": 1,
        "total_edges": 1,
    },
})

EMPTY_GRAPH_JSON = json.dumps({
    "nodes": [],
    "edges": [],
    "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0},
})


async def _create_job(
    db_session,
    user_id: str,
    graph_data: str | None,
    status: JobStatus = JobStatus.COMPLETED,
) -> SimulationJob:
    job = SimulationJob(
        user_id=user_id,
        seed_text="test seed",
        goal="test goal",
        tier="small",
        credits_charged=30,
        status=status,
        result_graph=graph_data,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Task 4 — Graph API endpoint tests
# ---------------------------------------------------------------------------

class TestGetGraphEndpoint:
    async def test_get_graph_returns_graph_data(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], VALID_GRAPH_JSON)

        resp = await client.get(
            f"/api/jobs/{job.id}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["name"] == "Alice"
        assert len(data["edges"]) == 1
        assert data["metadata"]["total_nodes"] == 1

    async def test_get_graph_returns_404_for_no_graph_data(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], None)

        resp = await client.get(
            f"/api/jobs/{job.id}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_get_graph_returns_404_for_nonexistent_job(self, client, auth_headers):
        resp = await client.get(
            "/api/jobs/99999/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_get_graph_returns_403_for_other_users_job(self, client, db_session, auth_headers):
        job = await _create_job(db_session, "other-user-id-999", VALID_GRAPH_JSON)

        resp = await client.get(
            f"/api/jobs/{job.id}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    async def test_get_graph_returns_401_without_auth(self, client, db_session):
        # No auth header at all
        resp = await client.get("/api/jobs/1/graph")
        assert resp.status_code == 401

    async def test_get_graph_handles_malformed_json(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], "not valid json{{{")

        resp = await client.get(
            f"/api/jobs/{job.id}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 500

    async def test_get_graph_with_empty_graph_json(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], EMPTY_GRAPH_JSON)

        resp = await client.get(
            f"/api/jobs/{job.id}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["metadata"]["total_nodes"] == 0
        assert data["metadata"]["total_edges"] == 0


# ---------------------------------------------------------------------------
# Task 5 — Graph data persistence
# ---------------------------------------------------------------------------

class TestGraphDataPersistence:
    async def test_graph_data_persisted_after_job_save(self, db_session):
        """Simulate the worker saving graph data via raw SQL (like _save_job_results)."""
        job = await _create_job(db_session, "user-123", None, status=JobStatus.PENDING)
        assert job.result_graph is None

        # Simulate the worker updating graph data via raw SQL
        await db_session.execute(
            text(
                "UPDATE simulation_jobs SET result_graph = :graph, status = :status WHERE id = :jid"
            ),
            {"graph": VALID_GRAPH_JSON, "status": JobStatus.COMPLETED.value, "jid": job.id},
        )
        await db_session.commit()

        # Re-read from DB
        await db_session.refresh(job)
        assert job.result_graph is not None
        parsed = json.loads(job.result_graph)
        assert parsed["nodes"][0]["name"] == "Alice"
        assert parsed["metadata"]["total_nodes"] == 1
