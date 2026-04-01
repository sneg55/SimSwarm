# Rich Simulation Data Extraction & Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract rich simulation data (posts, trades, market curves, agent trajectories) from GPU worker SQLite DBs and store in self-hosted MinIO object storage via presigned URLs.

**Architecture:** GPU worker extracts 8 JSON files from SQLite DBs after simulation completes, uploads to MinIO via presigned PUT URLs. SimSwarm generates upload URLs at job creation, passes through Celery. New API endpoint serves presigned download URLs to frontend. Upload failure is non-fatal — existing report/chat_log/graph_data flow unchanged.

**Tech Stack:** Python (minio SDK), MinIO (Docker), Flask (GPU worker), FastAPI (SimSwarm), Alembic, Celery

**Spec:** `docs/superpowers/specs/2026-04-01-rich-simulation-data-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `saas/storage/__init__.py` | Package init |
| Create | `saas/storage/minio_client.py` | Presigned URL generation (upload + download) |
| Create | `tests/test_minio_client.py` | Unit tests for storage client |
| Modify | `saas/config.py` | Add MINIO_* settings |
| Modify | `saas/models/job.py` | Add `sim_data_available` column |
| Create | `alembic/versions/m4n5o6p7q8r9_add_sim_data_available.py` | Migration |
| Modify | `saas/schemas/jobs.py` | Add `sim_data_available` to response schemas |
| Modify | `saas/api/jobs.py` | Generate upload URLs, new sim-data endpoint |
| Modify | `saas/workers/tasks.py` | Accept + forward `upload_urls` |
| Modify | `saas/workers/job_runner.py` | Add to JobConfig + `/job` POST body, update sim_data_available |
| Create | `infra/docker/sim_data_extractor.py` | 8 extraction functions (SQLite → JSON) |
| Modify | `infra/docker/worker_api.py` | Accept upload_urls, call extractor, upload to MinIO |
| Modify | `infra/docker/run_job.py` | Return simulation_id for DB access |
| Modify | `infra/docker/Dockerfile.worker` | Add `minio` pip dep (for upload, or just use `requests`) |
| Create | `tests/test_sim_data_api.py` | API endpoint tests |

---

### Task 1: MinIO storage client

**Files:**
- Create: `saas/storage/__init__.py`
- Create: `saas/storage/minio_client.py`
- Create: `tests/test_minio_client.py`
- Modify: `saas/config.py`

- [ ] **Step 1: Add MinIO settings to config**

In `saas/config.py`, add after the `MAX_SIMULATION_ROUNDS` line:

```python
    # MinIO object storage (rich simulation data)
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "simswarm"
    MINIO_SECURE: bool = True
```

- [ ] **Step 2: Write the test**

Create `tests/test_minio_client.py`:

```python
from unittest.mock import MagicMock, patch

from saas.storage.minio_client import SimDataStorage, SIM_DATA_FILES


def test_sim_data_files_list():
    """All 8 expected files are defined."""
    assert len(SIM_DATA_FILES) == 8
    assert "market_curves.json" in SIM_DATA_FILES
    assert "posts.json" in SIM_DATA_FILES
    assert "agent_trajectories.json" in SIM_DATA_FILES


def test_generate_upload_urls_returns_dict():
    """generate_upload_urls returns a URL per file."""
    mock_client = MagicMock()
    mock_client.presigned_put_object.return_value = "https://minio.example.com/presigned-put"

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"

    urls = storage.generate_upload_urls(job_id=42)

    assert len(urls) == 8
    assert all(url == "https://minio.example.com/presigned-put" for url in urls.values())
    assert "market_curves.json" in urls
    # Verify correct object path
    calls = mock_client.presigned_put_object.call_args_list
    first_call_args = calls[0]
    assert first_call_args[0][0] == "simswarm"  # bucket
    assert "sim-data/42/" in first_call_args[0][1]  # object name


def test_generate_download_urls_returns_dict():
    """generate_download_urls returns a URL per file."""
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "https://minio.example.com/presigned-get"

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"

    urls = storage.generate_download_urls(job_id=42)

    assert len(urls) == 8
    assert all(url == "https://minio.example.com/presigned-get" for url in urls.values())


def test_generate_upload_urls_disabled_when_no_endpoint():
    """Returns None when MinIO is not configured."""
    storage = SimDataStorage(endpoint="", access_key="", secret_key="", bucket="simswarm")
    result = storage.generate_upload_urls(job_id=1)
    assert result is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_minio_client.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Create storage package**

Create `saas/storage/__init__.py`:

```python
```

Create `saas/storage/minio_client.py`:

```python
"""MinIO object storage client for rich simulation data."""
from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

SIM_DATA_FILES = [
    "market_curves.json",
    "agent_trajectories.json",
    "engagement_summary.json",
    "top_posts.json",
    "posts.json",
    "trades.json",
    "social_graph.json",
    "profiles.json",
]

UPLOAD_EXPIRY = timedelta(hours=2)
DOWNLOAD_EXPIRY = timedelta(hours=1)


class SimDataStorage:
    """Generate presigned URLs for simulation data upload/download."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = True):
        self._bucket = bucket
        self._enabled = bool(endpoint)
        if self._enabled:
            from minio import Minio
            self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        else:
            self._client = None

    def _object_path(self, job_id: int, filename: str) -> str:
        return f"sim-data/{job_id}/{filename}"

    def generate_upload_urls(self, job_id: int) -> dict[str, str] | None:
        """Generate presigned PUT URLs for all sim data files. Returns None if MinIO not configured."""
        if not self._enabled:
            return None
        urls = {}
        for filename in SIM_DATA_FILES:
            obj = self._object_path(job_id, filename)
            urls[filename] = self._client.presigned_put_object(self._bucket, obj, expires=UPLOAD_EXPIRY)
        return urls

    def generate_download_urls(self, job_id: int) -> dict[str, str] | None:
        """Generate presigned GET URLs for all sim data files. Returns None if MinIO not configured."""
        if not self._enabled:
            return None
        urls = {}
        for filename in SIM_DATA_FILES:
            obj = self._object_path(job_id, filename)
            urls[filename] = self._client.presigned_get_object(self._bucket, obj, expires=DOWNLOAD_EXPIRY)
        return urls
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_minio_client.py -v`
Expected: ALL PASS

- [ ] **Step 6: Install minio SDK**

Run: `pip install minio`

Add to `pyproject.toml` or `requirements.txt` dependencies: `minio`

- [ ] **Step 7: Commit**

```bash
git add saas/storage/ saas/config.py tests/test_minio_client.py
git commit -m "feat: add MinIO storage client for simulation data"
```

---

### Task 2: DB migration + schema for sim_data_available

**Files:**
- Modify: `saas/models/job.py`
- Modify: `saas/schemas/jobs.py`
- Create: `alembic/versions/m4n5o6p7q8r9_add_sim_data_available.py`

- [ ] **Step 1: Add column to model**

In `saas/models/job.py`, add after the `enrichment_citations` column:

```python
    sim_data_available: Mapped[bool] = mapped_column(default=False)
```

- [ ] **Step 2: Add to response schemas**

In `saas/schemas/jobs.py`, add `sim_data_available: bool = False` to both `JobResponse` and `JobSummary` classes.

- [ ] **Step 3: Create migration**

Create `alembic/versions/m4n5o6p7q8r9_add_sim_data_available.py`:

```python
"""add sim_data_available column to simulation_jobs

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("sim_data_available", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "sim_data_available")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Verify alembic head**

Run: `alembic heads`
Expected: Single head `m4n5o6p7q8r9`

- [ ] **Step 6: Commit**

```bash
git add saas/models/job.py saas/schemas/jobs.py alembic/versions/m4n5o6p7q8r9_add_sim_data_available.py
git commit -m "feat: add sim_data_available column and schema field"
```

---

### Task 3: API — generate upload URLs + sim-data download endpoint

**Files:**
- Modify: `saas/api/jobs.py`
- Create: `tests/test_sim_data_api.py`

- [ ] **Step 1: Write the test**

Create `tests/test_sim_data_api.py`:

```python
from unittest.mock import patch, MagicMock


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.api.jobs.run_simulation_task.delay", return_value=mock_task)


async def test_sim_data_returns_404_when_not_available(client, auth_headers, funded_user, seeded_routing):
    """GET /api/jobs/{id}/sim-data returns 404 when sim_data_available is false."""
    with _mock_delay():
        create_resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"seed_text": "Test seed text for simulation.", "goal": "Test goal", "tier": "small"},
        )
    job_id = create_resp.json()["id"]

    response = await client.get(f"/api/jobs/{job_id}/sim-data", headers=auth_headers)
    assert response.status_code == 404


async def test_sim_data_returns_404_for_nonexistent_job(client, auth_headers):
    """GET /api/jobs/99999/sim-data returns 404."""
    response = await client.get("/api/jobs/99999/sim-data", headers=auth_headers)
    assert response.status_code == 404


async def test_sim_data_requires_auth(client):
    """GET /api/jobs/1/sim-data returns 401 without auth."""
    response = await client.get("/api/jobs/1/sim-data")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sim_data_api.py -v`
Expected: FAIL — 404 on route (endpoint doesn't exist yet)

- [ ] **Step 3: Add sim-data endpoint to jobs API**

In `saas/api/jobs.py`, add the endpoint and storage initialization. At the top of the file, add import:

```python
from saas.storage.minio_client import SimDataStorage
```

Add a helper to get the storage client (after the router definition):

```python
def _get_sim_data_storage(request: Request) -> SimDataStorage:
    settings = request.app.state.settings
    return SimDataStorage(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        bucket=settings.MINIO_BUCKET,
        secure=settings.MINIO_SECURE,
    )
```

Add the endpoint:

```python
@router.get("/{job_id}/sim-data")
async def get_sim_data(
    request: Request,
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return presigned download URLs for rich simulation data."""
    user_id = current_user["user_id"]
    result = await session.execute(
        select(SimulationJob).where(SimulationJob.id == job_id, SimulationJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job or not job.sim_data_available:
        raise HTTPException(status_code=404, detail="Simulation data not available")

    storage = _get_sim_data_storage(request)
    urls = storage.generate_download_urls(job_id=job_id)
    if not urls:
        raise HTTPException(status_code=404, detail="Object storage not configured")

    return {"job_id": job_id, "files": urls}
```

- [ ] **Step 4: Generate upload URLs at job creation and pass to Celery**

In the `create_job` function in `saas/api/jobs.py`, after generating the job ID (after `await session.flush()`), add:

```python
    # Generate presigned upload URLs for rich simulation data
    storage = _get_sim_data_storage(request)
    upload_urls = storage.generate_upload_urls(job_id=job.id)
```

Add `upload_urls=upload_urls,` to the `run_simulation_task.delay()` call.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_sim_data_api.py tests/test_jobs_api.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add saas/api/jobs.py tests/test_sim_data_api.py
git commit -m "feat: add sim-data API endpoint and upload URL generation"
```

---

### Task 4: Pass upload_urls through Celery → JobConfig → GPU worker

**Files:**
- Modify: `saas/workers/tasks.py`
- Modify: `saas/workers/job_runner.py`
- Modify: `saas/workers/persistence.py`

- [ ] **Step 1: Add upload_urls to Celery task**

In `saas/workers/tasks.py`, add `upload_urls: dict | None = None,` parameter to `run_simulation_task` (after `forecast_days`).

Pass to JobConfig:

```python
        upload_urls=upload_urls,
```

- [ ] **Step 2: Add to JobConfig dataclass**

In `saas/workers/job_runner.py`, add to `JobConfig` (at the end, with default):

```python
    upload_urls: dict | None = None
```

- [ ] **Step 3: Pass upload_urls in /job POST body**

In `saas/workers/job_runner.py`, update the `_execute_pipeline` method's POST payload:

```python
            resp = await client.post(f"{worker_url}/job", json={
                "seed_text": config.seed_text,
                "goal": config.goal,
                "max_rounds": config.max_rounds,
                "forecast_days": config.forecast_days,
                "upload_urls": config.upload_urls,
            }, timeout=30)
```

- [ ] **Step 4: Update sim_data_available from /status response**

In `saas/workers/job_runner.py`, in the `_poll_until_complete` method, after the `status == "completed"` block where result is assigned, add `sim_data_uploaded` to the return dict:

Find the return dict at the end of `_execute_pipeline` (around line 369-377) and add:

```python
            "sim_data_uploaded": result.get("sim_data_uploaded", False),
```

- [ ] **Step 5: Add persistence function for sim_data_available**

In `saas/workers/persistence.py`, add:

```python
def _update_sim_data_available(job_id: int, available: bool) -> None:
    """Mark whether rich simulation data was uploaded to MinIO."""
    engine = _get_sync_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET sim_data_available = :available WHERE id = :job_id"),
                {"available": available, "job_id": job_id},
            )
            conn.commit()
    finally:
        engine.dispose()
```

- [ ] **Step 6: Call persistence in tasks.py**

In `saas/workers/tasks.py`, in `run_simulation_task`, after `_save_job_results(...)`, add:

```python
        # Mark rich simulation data availability
        sim_data_uploaded = result.get("sim_data_uploaded", False)
        if sim_data_uploaded:
            _update_sim_data_available(job_id, True)
```

Add the import at the top of `tasks.py`:

```python
from saas.workers.persistence import _update_sim_data_available
```

(Add it alongside the existing persistence imports.)

- [ ] **Step 7: Run backend tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add saas/workers/tasks.py saas/workers/job_runner.py saas/workers/persistence.py
git commit -m "feat: pass upload_urls through Celery to GPU worker, track sim_data_available"
```

---

### Task 5: GPU worker — data extraction functions

**Files:**
- Create: `infra/docker/sim_data_extractor.py`

This is the core extraction logic. All functions take a simulation directory path and return Python dicts/lists ready for JSON serialization.

- [ ] **Step 1: Create sim_data_extractor.py**

Create `infra/docker/sim_data_extractor.py`:

```python
"""Extract rich simulation data from MiroShark SQLite databases.

All functions open DBs read-only and return JSON-serializable dicts/lists.
Used by worker_api.py after simulation completes, before pod termination.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# Sentiment word lists (matching run_job.py's score_entity_sentiment)
_POSITIVE = {"good", "great", "strong", "positive", "support", "gain", "rise", "up", "growth",
             "success", "win", "benefit", "improve", "surge", "rally", "boost", "confident",
             "optimistic", "bullish", "recovery", "progress", "opportunity"}
_NEGATIVE = {"bad", "poor", "weak", "negative", "loss", "fall", "down", "decline", "fail",
             "crash", "risk", "fear", "drop", "crisis", "concern", "threat", "bearish",
             "pessimistic", "collapse", "danger", "trouble", "panic"}


def _open_db(path: str) -> sqlite3.Connection | None:
    """Open SQLite DB read-only. Returns None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _dict_rows(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    """Execute query and return list of dicts."""
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _sentiment_score(text: str) -> float:
    """Simple lexicon-based sentiment score for a text string."""
    words = set(text.lower().split())
    pos = len(words & _POSITIVE)
    neg = len(words & _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def extract_posts(sim_dir: str) -> list[dict]:
    """Extract all posts from Twitter + Reddit DBs with engagement counts."""
    posts = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, """
                SELECT p.post_id, p.user_id, u.agent_id, u.user_name AS agent_name,
                       p.content, p.created_at, p.num_likes, p.num_dislikes,
                       p.num_shares, p.num_reports, p.original_post_id
                FROM post p JOIN user u ON p.user_id = u.user_id
                ORDER BY p.created_at
            """)
            for r in rows:
                r["platform"] = platform
            posts.extend(rows)
        finally:
            conn.close()
    return posts


def extract_trades(sim_dir: str) -> list[dict]:
    """Extract all prediction market trades."""
    db_path = os.path.join(sim_dir, "polymarket_simulation.db")
    conn = _open_db(db_path)
    if not conn:
        return []
    try:
        return _dict_rows(conn, """
            SELECT t.trade_id, t.user_id, u.user_name AS agent_name, u.agent_id,
                   t.market_id, t.side, t.outcome, t.shares, t.price, t.cost, t.created_at
            FROM trade t JOIN user u ON t.user_id = u.user_id
            ORDER BY t.created_at
        """)
    finally:
        conn.close()


def extract_market_curves(sim_dir: str) -> list[dict]:
    """Reconstruct market price curves from trade history + initial reserves."""
    db_path = os.path.join(sim_dir, "polymarket_simulation.db")
    conn = _open_db(db_path)
    if not conn:
        return []
    try:
        markets = _dict_rows(conn, "SELECT market_id, question, outcome_a, outcome_b, reserve_a, reserve_b FROM market")
        trades = _dict_rows(conn, "SELECT market_id, side, outcome, shares, price, cost, created_at FROM trade ORDER BY created_at")
    finally:
        conn.close()

    # Build price timeline per market
    curves = []
    for market in markets:
        mid = market["market_id"]
        ra, rb = market["reserve_a"], market["reserve_b"]
        # Initial price point
        price_yes = rb / (ra + rb) if (ra + rb) > 0 else 0.5
        points = [{"trade_idx": 0, "price_yes": round(price_yes, 4), "price_no": round(1 - price_yes, 4), "volume": 0}]

        market_trades = [t for t in trades if t["market_id"] == mid]
        cumulative_volume = 0.0
        for i, t in enumerate(market_trades):
            cumulative_volume += abs(t.get("cost", 0))
            # Recalculate reserves from trade
            if t["side"] == "buy":
                if t["outcome"] == market["outcome_a"]:
                    ra -= t["shares"]
                    rb += t["cost"]
                else:
                    rb -= t["shares"]
                    ra += t["cost"]
            else:  # sell
                if t["outcome"] == market["outcome_a"]:
                    ra += t["shares"]
                    rb -= t["cost"]
                else:
                    rb += t["shares"]
                    ra -= t["cost"]
            price_yes = rb / (ra + rb) if (ra + rb) > 0 else 0.5
            points.append({
                "trade_idx": i + 1,
                "price_yes": round(price_yes, 4),
                "price_no": round(1 - price_yes, 4),
                "volume": round(cumulative_volume, 2),
            })

        curves.append({
            "market_id": mid,
            "question": market["question"],
            "outcome_a": market["outcome_a"],
            "outcome_b": market["outcome_b"],
            "points": points,
        })
    return curves


def extract_agent_trajectories(sim_dir: str, actions: list[dict], round_window: int = 20) -> list[dict]:
    """Per-agent metrics aggregated by round windows, including derived sentiment."""
    # Build agent info from DBs
    agents = {}
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            for row in _dict_rows(conn, "SELECT agent_id, user_name, name FROM user"):
                aid = row["agent_id"]
                if aid not in agents:
                    agents[aid] = {"agent_id": aid, "name": row["user_name"] or row["name"], "rounds": []}
        finally:
            conn.close()

    if not agents or not actions:
        return list(agents.values())

    # Determine max round
    max_round = max((a.get("round_num", a.get("round", 0)) for a in actions), default=0)

    # Aggregate per agent per window
    for aid, agent in agents.items():
        for win_start in range(0, max_round + 1, round_window):
            win_end = win_start + round_window
            window_actions = [a for a in actions
                             if a.get("agent_id") == aid
                             and win_start <= (a.get("round_num", a.get("round", 0))) < win_end]
            posts = [a for a in window_actions if a.get("action_type") == "CREATE_POST"]
            post_texts = " ".join(
                a.get("action_args", {}).get("content", "") for a in posts if isinstance(a.get("action_args"), dict)
            )
            agent["rounds"].append({
                "round": win_start,
                "posts": len(posts),
                "actions": len(window_actions),
                "sentiment": _sentiment_score(post_texts) if post_texts else 0.0,
            })

    return list(agents.values())


def extract_engagement_summary(actions: list[dict], round_window: int = 10) -> list[dict]:
    """Per-round-window engagement totals."""
    if not actions:
        return []
    max_round = max((a.get("round_num", a.get("round", 0)) for a in actions), default=0)
    summary = []
    for win_start in range(0, max_round + 1, round_window):
        win_end = win_start + round_window
        window = [a for a in actions if win_start <= (a.get("round_num", a.get("round", 0))) < win_end]
        posts = sum(1 for a in window if a.get("action_type") == "CREATE_POST")
        likes = sum(1 for a in window if a.get("action_type") in ("LIKE_POST", "LIKE_COMMENT"))
        comments = sum(1 for a in window if a.get("action_type") == "CREATE_COMMENT")
        active = len(set(a.get("agent_id") for a in window))
        summary.append({
            "round": win_start,
            "total_posts": posts,
            "total_likes": likes,
            "total_comments": comments,
            "active_agents": active,
        })
    return summary


def extract_top_posts(sim_dir: str, limit: int = 50) -> list[dict]:
    """Top posts by engagement across all platforms."""
    posts = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, f"""
                SELECT p.post_id, u.agent_id, u.user_name AS agent_name,
                       p.content, p.created_at,
                       p.num_likes, p.num_dislikes, p.num_shares,
                       (p.num_likes + p.num_shares) AS engagement
                FROM post p JOIN user u ON p.user_id = u.user_id
                WHERE p.content != ''
                ORDER BY engagement DESC
                LIMIT {limit}
            """)
            for r in rows:
                r["platform"] = platform
            posts.extend(rows)
        finally:
            conn.close()
    posts.sort(key=lambda p: p.get("engagement", 0), reverse=True)
    return posts[:limit]


def extract_social_graph(sim_dir: str) -> dict:
    """Follow edges + detected coalitions from mutual follows."""
    edges = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, """
                SELECT f.follower_id, u1.user_name AS follower_name,
                       f.followee_id, u2.user_name AS followee_name,
                       f.created_at
                FROM follow f
                JOIN user u1 ON f.follower_id = u1.user_id
                JOIN user u2 ON f.followee_id = u2.user_id
            """)
            for r in rows:
                r["platform"] = platform
            edges.extend(rows)
        finally:
            conn.close()

    # Detect mutual follows (coalitions)
    pairs = set()
    for e in edges:
        pairs.add((e["follower_id"], e["followee_id"]))
    mutual = []
    seen = set()
    for a, b in pairs:
        if (b, a) in pairs and (min(a, b), max(a, b)) not in seen:
            seen.add((min(a, b), max(a, b)))
            mutual.append({"agent_a": a, "agent_b": b})

    return {"edges": edges, "mutual_follows": mutual}


def extract_profiles(sim_dir: str) -> list[dict]:
    """Agent profiles from pre-simulation CSV/JSON files."""
    profiles = []

    # Reddit profiles (JSON)
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.exists(reddit_path):
        with open(reddit_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                profiles = data

    # Twitter profiles (CSV) — merge into profiles
    twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
    if os.path.exists(twitter_path):
        import csv
        with open(twitter_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try to match by agent name and merge
                agent_name = row.get("user_name", row.get("name", ""))
                matched = False
                for p in profiles:
                    if p.get("user_name") == agent_name or p.get("name") == agent_name:
                        p["twitter_profile"] = row
                        matched = True
                        break
                if not matched:
                    profiles.append({"name": agent_name, "twitter_profile": row})

    return profiles


def extract_all(sim_dir: str, actions: list[dict]) -> dict[str, object]:
    """Run all extractors and return a dict of filename → data."""
    return {
        "market_curves.json": extract_market_curves(sim_dir),
        "agent_trajectories.json": extract_agent_trajectories(sim_dir, actions),
        "engagement_summary.json": extract_engagement_summary(actions),
        "top_posts.json": extract_top_posts(sim_dir),
        "posts.json": extract_posts(sim_dir),
        "trades.json": extract_trades(sim_dir),
        "social_graph.json": extract_social_graph(sim_dir),
        "profiles.json": extract_profiles(sim_dir),
    }
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/sim_data_extractor.py
git commit -m "feat: add simulation data extraction functions (8 extractors)"
```

---

### Task 6: GPU worker — upload extracted data to MinIO

**Files:**
- Modify: `infra/docker/worker_api.py`
- Modify: `infra/docker/run_job.py`

- [ ] **Step 1: Update run_job.py to return simulation_id**

In `infra/docker/run_job.py`, in the `run_pipeline` function, add `simulation_id` to the returned summary dict (around line 927):

```python
    summary = {
        "status": "completed",
        "simulation_id": simulation_id,
        "graph_id": graph_id,
        "report_length": len(report_md),
        "chat_log_entries": len(chat_log),
        "graph_nodes": graph_data["metadata"]["total_nodes"],
        "graph_edges": graph_data["metadata"]["total_edges"],
        "sim_dir": str(Path(SimulationRunner.RUN_STATE_DIR) / simulation_id),
    }
```

(The `simulation_id` is already in the summary; we just need to add `sim_dir`.)

- [ ] **Step 2: Update worker_api.py to accept upload_urls, extract, and upload**

Replace the `_run_pipeline` function in `infra/docker/worker_api.py`:

```python
def _run_pipeline(seed_text, goal, max_rounds, forecast_days=None, upload_urls=None):
    """Run MiroFish pipeline in background, stream output to log file."""
    try:
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        # Clear previous log
        LOG_FILE.write_text("")

        # Build CLI args
        cmd = [
            "python3", "-u", "/app/run_job.py",
            "--seed-file", str(seed_file),
            "--goal", goal,
            "--max-rounds", str(max_rounds),
            "--output-dir", "/tmp/results",
        ]

        env = {**os.environ}
        if forecast_days is not None:
            env["FORECAST_DAYS"] = str(forecast_days)

        with open(LOG_FILE, "w") as log_fh:
            proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, env=env)
            proc.wait(timeout=3600)

        log_content = LOG_FILE.read_text()

        if proc.returncode != 0:
            with _lock:
                _job["status"] = "failed"
                _job["error"] = log_content[-5000:]
            return

        # Read results
        results_dir = Path("/tmp/results")
        report = ""
        chat_log = "[]"
        graph_data = "{}"
        if (results_dir / "report.md").exists():
            report = (results_dir / "report.md").read_text()
        if (results_dir / "chat_log.json").exists():
            chat_log = (results_dir / "chat_log.json").read_text()
        if (results_dir / "graph_data.json").exists():
            graph_data = (results_dir / "graph_data.json").read_text()

        structured = "{}"
        if (results_dir / "structured_results.json").exists():
            structured = (results_dir / "structured_results.json").read_text()

        # Extract and upload rich simulation data
        sim_data_uploaded = False
        if upload_urls:
            try:
                sim_data_uploaded = _extract_and_upload(results_dir, chat_log, upload_urls)
            except Exception as exc:
                print(f"[worker] WARNING: sim data extraction/upload failed: {exc}", flush=True)

        with _lock:
            _job["status"] = "completed"
            _job["result"] = {
                "report": report,
                "chat_log": chat_log,
                "graph_data": graph_data,
                "structured": structured,
                "sim_data_uploaded": sim_data_uploaded,
            }

    except subprocess.TimeoutExpired:
        proc.kill()
        with _lock:
            _job["status"] = "failed"
            _job["error"] = "Job timed out after 1 hour"
    except Exception as e:
        with _lock:
            _job["status"] = "failed"
            _job["error"] = str(e)


def _extract_and_upload(results_dir, chat_log_str, upload_urls):
    """Extract data from SQLite DBs and upload to MinIO via presigned URLs."""
    import json as _json
    from sim_data_extractor import extract_all

    # Find simulation directory from summary
    summary_path = results_dir / "summary.json"
    if not summary_path.exists():
        print("[worker] No summary.json, skipping sim data extraction", flush=True)
        return False

    summary = _json.loads(summary_path.read_text())
    sim_dir = summary.get("sim_dir", "")
    if not sim_dir or not os.path.isdir(sim_dir):
        print(f"[worker] sim_dir not found: {sim_dir}", flush=True)
        return False

    # Parse actions from chat_log
    actions = _json.loads(chat_log_str) if isinstance(chat_log_str, str) else chat_log_str

    print(f"[worker] Extracting simulation data from {sim_dir}", flush=True)
    all_data = extract_all(sim_dir, actions)

    uploaded = 0
    for filename, url in upload_urls.items():
        if filename not in all_data:
            continue
        data = all_data[filename]
        body = _json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        try:
            resp = requests.put(url, data=body, headers={"Content-Type": "application/json"}, timeout=60)
            if resp.status_code in (200, 204):
                uploaded += 1
                print(f"[worker] Uploaded {filename} ({len(body)} bytes)", flush=True)
            else:
                print(f"[worker] Upload failed for {filename}: HTTP {resp.status_code}", flush=True)
        except Exception as exc:
            print(f"[worker] Upload failed for {filename}: {exc}", flush=True)

    print(f"[worker] Uploaded {uploaded}/{len(upload_urls)} sim data files", flush=True)
    return uploaded > 0
```

- [ ] **Step 3: Update submit_job to accept new fields**

In `infra/docker/worker_api.py`, update the `submit_job` route:

```python
@app.route("/job", methods=["POST"])
def submit_job():
    """Start pipeline in background. Returns immediately."""
    data = request.json or {}
    seed_text = data.get("seed_text", "")
    goal = data.get("goal", "")
    max_rounds = data.get("max_rounds", 200)
    forecast_days = data.get("forecast_days")
    upload_urls = data.get("upload_urls")

    with _lock:
        if _job["status"] == "running":
            return jsonify({"error": "A job is already running"}), 409
        _job["status"] = "running"
        _job["result"] = None
        _job["error"] = None

    LOG_FILE.write_text("")

    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds, forecast_days, upload_urls),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "accepted"})
```

- [ ] **Step 4: Update /status to include sim_data_uploaded**

In the `job_status` route, add `sim_data_uploaded`:

```python
@app.route("/status", methods=["GET"])
def job_status():
    """Poll for completion. Returns report + chat_log when done."""
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["report"] = _job["result"]["report"]
            resp["chat_log"] = _job["result"]["chat_log"]
            resp["graph_data"] = _job["result"].get("graph_data", "{}")
            resp["structured"] = _job["result"].get("structured", "{}")
            resp["sim_data_uploaded"] = _job["result"].get("sim_data_uploaded", False)
        if _job["status"] == "failed":
            resp["error"] = _job["error"]
    return jsonify(resp)
```

- [ ] **Step 5: Commit**

```bash
git add infra/docker/worker_api.py infra/docker/run_job.py
git commit -m "feat: GPU worker extracts sim data and uploads to MinIO via presigned URLs"
```

---

### Task 7: Full test suite + build verification

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Verify alembic single head**

Run: `alembic heads`
Expected: Single head `m4n5o6p7q8r9`

- [ ] **Step 5: Verify Docker worker image builds**

Run: `docker build -f infra/docker/Dockerfile.worker -t simswarm-worker:test .`
Expected: Build succeeds (sim_data_extractor.py is copied with the rest of infra/docker/)
