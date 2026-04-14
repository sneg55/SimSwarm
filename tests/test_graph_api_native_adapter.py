"""Tests for the graph adapter that transforms native-engine graph payloads
into the Graphiti-compatible shape the Vue frontend consumes.

Post-MiroShark cutover, ``simswarm/graph.py`` emits nodes with ``id``,
``group``, and edges with ``source``/``target`` — the frontend (GraphCanvas,
GraphDetailPanel) still reads the pre-cutover field names (``uuid``,
``labels``, ``source_node_uuid``/``target_node_uuid``, ``source_node_name``
/``target_node_name``). The API-layer adapter translates at the boundary so
neither side has to change.
"""
from __future__ import annotations

import json

from saas.jobs.models import SimulationJob, JobStatus


NATIVE_GRAPH_JSON = json.dumps({
    "nodes": [
        {
            "id": "alice",
            "label": "Alice",
            "group": "person",
            "summary": "A test node",
            "total_actions": 5,
            "total_posts": 2,
            "rounds_active": 3,
        },
        {
            "id": "bob",
            "label": "Bob",
            "group": "person",
            "summary": "Second node",
            "total_actions": 2,
            "total_posts": 1,
            "rounds_active": 2,
        },
    ],
    "edges": [
        {"source": "alice", "target": "bob", "type": "mention", "weight": 2},
    ],
    "metadata": {"total_nodes": 2, "total_edges": 1, "total_rounds": 3},
})


GRAPHITI_GRAPH_JSON = json.dumps({
    "nodes": [{
        "uuid": "n1",
        "name": "Alice",
        "labels": ["Person"],
        "summary": "A test node",
        "connection_count": 1,
    }],
    "edges": [{
        "uuid": "e1",
        "name": "knows",
        "fact": "Alice knows Bob",
        "source_node_uuid": "n1",
        "target_node_uuid": "n2",
        "source_node_name": "Alice",
        "target_node_name": "Bob",
    }],
    "metadata": {"total_nodes": 1, "total_edges": 1},
})


async def _create_job(db_session, user_id: str, graph_data: str | None) -> SimulationJob:
    job = SimulationJob(
        user_id=user_id, seed_text="s", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, result_graph=graph_data,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


class TestNativeGraphAdaptation:
    async def test_native_nodes_gain_uuid_alias(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], NATIVE_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        assert resp.status_code == 200
        nodes = resp.json()["nodes"]
        assert nodes[0]["uuid"] == "alice"
        assert nodes[0]["name"] == "Alice"

    async def test_native_nodes_gain_labels_array(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], NATIVE_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        nodes = resp.json()["nodes"]
        assert isinstance(nodes[0]["labels"], list)
        assert "person" in nodes[0]["labels"]

    async def test_native_nodes_gain_connection_count(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], NATIVE_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        by_id = {n["id"]: n for n in resp.json()["nodes"]}
        # one edge alice→bob ⇒ each gets connection_count=1
        assert by_id["alice"]["connection_count"] == 1
        assert by_id["bob"]["connection_count"] == 1

    async def test_native_nodes_gain_sentiment_default(self, client, db_session, auth_headers):
        job = await _create_job(db_session, auth_headers["_user_id"], NATIVE_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        for n in resp.json()["nodes"]:
            assert "sentiment" in n
            assert isinstance(n["sentiment"], (int, float))

    async def test_native_edges_gain_uuid_and_name_aliases(
        self, client, db_session, auth_headers,
    ):
        job = await _create_job(db_session, auth_headers["_user_id"], NATIVE_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        e = resp.json()["edges"][0]
        assert e["source_node_uuid"] == "alice"
        assert e["target_node_uuid"] == "bob"
        assert e["source_node_name"] == "Alice"
        assert e["target_node_name"] == "Bob"
        assert e["name"] == "mention"  # the old frontend uses `name` for edge label

    async def test_graphiti_payload_passes_through_unchanged(
        self, client, db_session, auth_headers,
    ):
        """Already-Graphiti-shaped payloads (pre-cutover jobs like #97) must
        pass through untouched so old jobs still render."""
        job = await _create_job(db_session, auth_headers["_user_id"], GRAPHITI_GRAPH_JSON)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        data = resp.json()
        assert data["nodes"][0]["uuid"] == "n1"
        assert data["nodes"][0]["labels"] == ["Person"]
        assert data["edges"][0]["source_node_uuid"] == "n1"

    async def test_empty_native_graph_adapted_safely(
        self, client, db_session, auth_headers,
    ):
        payload = json.dumps({"nodes": [], "edges": [], "metadata": {}})
        job = await _create_job(db_session, auth_headers["_user_id"], payload)
        resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
