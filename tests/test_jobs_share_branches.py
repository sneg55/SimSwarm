"""Coverage for saas.jobs.share (public share endpoints)."""
import json

from saas.jobs.models import SimulationJob, JobStatus


async def test_demos_no_user(client):
    """With no demo@fishcloud.internal user, returns []."""
    resp = await client.get("/api/share/demos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_demos_with_shared_jobs(client, db_session):
    """Create a demo user and a shared job; demos endpoint lists it."""
    from saas.auth.models import User
    user = User(
        email="demo@fishcloud.internal",
        password_hash="x",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    job = SimulationJob(
        user_id=str(user.id), seed_text="x", goal="Demo Goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="demo-token", result_report="# Content",
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/demos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Demo Goal"
    assert data[0]["share_token"] == "demo-token"


async def test_shared_og_not_found(client):
    resp = await client.get("/api/share/no-such-token/og")
    assert resp.status_code == 404


async def test_shared_og_uses_key_insight(client, db_session):
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="Test Goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="og-token", key_insight="This is the key insight for testing.",
        result_report="# Report",
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/og-token/og")
    assert resp.status_code == 200
    body = resp.text
    assert "Test Goal" in body
    assert "key insight" in body.lower()


async def test_shared_og_falls_back_to_report(client, db_session):
    """No key_insight -> extract first meaningful paragraph."""
    report = (
        "# Heading\n"
        "Short.\n"
        "This is a substantial paragraph that should be used for the OG meta description.\n"
    )
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="Goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="og2", key_insight=None, result_report=report,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/og2/og")
    assert resp.status_code == 200
    assert "substantial paragraph" in resp.text


async def test_shared_og_no_content(client, db_session):
    """No key_insight or report -> synthesized default description."""
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="Bare Goal", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="og3", key_insight=None, result_report=None,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/og3/og")
    assert resp.status_code == 200
    assert "Bare Goal" in resp.text


async def test_shared_graph_not_found(client):
    resp = await client.get("/api/share/no-token/graph")
    assert resp.status_code == 404


async def test_shared_graph_no_data(client, db_session):
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="g-no", result_graph=None,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/g-no/graph")
    assert resp.status_code == 404


async def test_shared_graph_invalid_json(client, db_session):
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="g-bad", result_graph="not-json{",
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/g-bad/graph")
    assert resp.status_code == 500


async def test_shared_result_with_chat_log(client, db_session):
    """Shared result parses chat_log and graph JSON."""
    job = SimulationJob(
        user_id="u1", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        share_token="r-tok",
        result_chat_log=json.dumps([{"action": "post"}]),
        result_graph=json.dumps({"nodes": []}),
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get("/api/share/r-tok")
    assert resp.status_code == 200
    data = resp.json()
    assert data["chat_log"] == [{"action": "post"}]
    # Graph is returned in the frontend-adapted shape (adapt_graph_payload
    # backfills edges/metadata), not the raw stored JSON.
    assert data["graph"] == {"nodes": [], "edges": [], "metadata": {}}
