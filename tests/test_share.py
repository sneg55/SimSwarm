from saas.jobs.models import SimulationJob, JobStatus


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


async def test_shared_result_includes_structured_data(client, auth_headers, db_session):
    """Shared result includes structured data when present."""
    import json
    from saas.jobs.models import SimulationJob, JobStatus
    structured = json.dumps({"brief": "Test brief", "findings": []})
    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test", goal="Test Goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report", result_chat_log="[]",
        result_structured=structured,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Create share link
    share_resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]

    # Access shared result
    resp = await client.get(f"/api/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Goal"
    assert data["structured"]["brief"] == "Test brief"
    assert data["graph"] is None  # No graph data set


async def test_shared_result_graph_is_adapted_for_frontend(client, auth_headers, db_session):
    """The combined /share/{token} payload must return the graph in the
    Graphiti shape the frontend reads (uuid/name on nodes; source_node_uuid,
    source_node_name, name, fact on edges) — not the raw native-engine shape.
    Regression: shared/demo graphs rendered nodes but no edges/relationships
    because get_shared_result returned the un-adapted graph."""
    import json
    from saas.jobs.models import SimulationJob, JobStatus
    # Raw native-engine shape (no uuid/name; edges use source/target/type)
    graph = json.dumps({
        "nodes": [
            {"id": "n1", "label": "Alice", "group": "Person"},
            {"id": "n2", "label": "Bob", "group": "Person"},
        ],
        "edges": [{"source": "n1", "target": "n2", "type": "mention", "weight": 3}],
        "metadata": {"total_nodes": 2, "total_edges": 1},
    })
    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test", goal="test", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report", result_chat_log="[]",
        result_graph=graph,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    share_resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/share/{token}")
    assert resp.status_code == 200
    g = resp.json()["graph"]
    edge = g["edges"][0]
    assert edge["source_node_uuid"] == "n1"
    assert edge["target_node_uuid"] == "n2"
    assert edge["source_node_name"] == "Alice"
    assert edge["target_node_name"] == "Bob"
    assert edge["name"] == "mention"
    assert edge["fact"] == "mention"
    node = g["nodes"][0]
    assert node["uuid"] == "n1"
    assert node["name"] == "Alice"


async def test_shared_graph_endpoint(client, auth_headers, db_session):
    """Shared graph endpoint returns graph data."""
    import json
    from saas.jobs.models import SimulationJob, JobStatus
    graph = json.dumps({"nodes": [{"uuid": "n1", "name": "A"}], "edges": [], "metadata": {"total_nodes": 1, "total_edges": 0}})
    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test", goal="test", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report", result_chat_log="[]",
        result_graph=graph,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    share_resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/share/{token}/graph")
    assert resp.status_code == 200
    assert resp.json()["metadata"]["total_nodes"] == 1
