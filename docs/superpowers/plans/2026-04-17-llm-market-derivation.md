# LLM-Derived Prediction Markets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before a sim runs, call an LLM to derive 3–5 binary prediction markets from the user's goal + enriched seed, persist them on the job row, and pass them to the GPU pod so the market env actually has markets to trade on. Surface the derived markets (with rationales) in the data dashboard.

**Architecture:** New CPU-side Celery step `derive_markets_from_goal` runs after enrichment inside `run_simulation_task`. Result stored on a new `SimulationJob.markets_config` JSON column. Propagated to the pod via a new `markets_config` field in `JobConfig`, shipped over the existing `/job` POST payload, written to `/tmp/markets.json` on the pod, consumed by `run_job_v2.py --markets-config-file`, and passed into `EnvironmentConfig(type="market", params={"markets": …})`. Frontend renders a new `MarketsList.vue` component in the data dashboard.

**Tech Stack:** Python 3.11+, async SQLAlchemy + Alembic, Celery, Flask (pod API), xAI Grok via the existing enrichment client pattern, Vue 3 Composition API, Vitest.

**Spec:** [2026-04-17-llm-market-derivation-design.md](../specs/2026-04-17-llm-market-derivation-design.md). All five design decisions are locked in that doc — this plan assumes them.

---

## File Structure

**Create:**
- `saas/jobs/market_derivation.py` — LLM call + JSON parsing + validation + tier cap + fallback. One public function: `derive_markets(goal: str, enriched_seed: str, tier: str) -> list[dict]`.
- `alembic/versions/w4x5y6z7a8b9_add_markets_config.py` — migration that adds the JSON column.
- `frontend/src/components/data/MarketsList.vue` — renders the derived-markets panel.
- `frontend/src/components/data/__tests__/MarketsList.spec.js` — vitest coverage.
- `tests/jobs/test_market_derivation.py` — unit tests for the deriver.
- `tests/jobs/test_markets_config_persistence.py` — tests for the sync update helper.

**Modify:**
- `saas/jobs/models.py` — add `markets_config: Mapped[list[dict] | None]` to `SimulationJob`.
- `saas/jobs/persistence_sync_progress.py` — add `_update_markets_config_sync`.
- `saas/jobs/persistence.py` — re-export `_update_markets_config_sync` and alias it as `_update_markets_config`.
- `saas/jobs/config.py` — add `markets_config: list[dict] | None = None` to `JobConfig`.
- `saas/jobs/pipeline.py` — include `markets_config` in the `submit_job` POST body.
- `saas/jobs/tasks.py::run_simulation_task` — call deriver after enrichment, persist, pass through.
- `saas/jobs/schemas.py::JobResponse` — add `markets_config: list[dict] | None = None`.
- `infra/docker/worker_api.py` — accept `markets_config` on `/job`, write it to `/tmp/markets.json`, add `--markets-config-file` to the subprocess argv.
- `infra/docker/run_job_v2.py` — new CLI arg + wiring to `run_pipeline`.
- `infra/docker/run_job_v2_runner.py::run_simulation` — new optional `markets_config` arg plumbed into `EnvironmentConfig`.
- `frontend/src/components/data/DataDashboard.vue` — new `markets` prop; render `<MarketsList>` above `<TradeFeed>`.
- `frontend/src/views/SimulationResults.vue` — pass `:markets="job?.markets_config"` through.

**Ground rules for executors:**
- TDD. Write the failing test first. Verify it fails for the right reason before implementing.
- Commit after each task's tests pass. One logical change per commit.
- Never `--no-verify`. If a hook fails, fix the root cause and commit again.
- Stay inside the task's listed files. If you need to touch something else, STOP and report.

---

## Task 1: Add `markets_config` column + persistence helper

**Files:**
- Modify: `saas/jobs/models.py:54` (append new column)
- Create: `alembic/versions/w4x5y6z7a8b9_add_markets_config.py`
- Modify: `saas/jobs/persistence_sync_progress.py` (append new helper)
- Modify: `saas/jobs/persistence.py` (re-export)
- Create: `tests/jobs/test_markets_config_persistence.py`

- [ ] **Step 1: Read the latest migration to confirm the revision ID pattern**

Run: `ls alembic/versions/ | tail -3`

Expected: shows e.g. `v3w4x5y6z7a8_add_reporting_status.py` as the newest. Note the revision prefix pattern (8-char base-36 identifier). New revision ID: `w4x5y6z7a8b9` (next in the sequence).

- [ ] **Step 2: Write the failing persistence test**

Create `tests/jobs/test_markets_config_persistence.py`:

```python
"""Unit tests for markets_config persistence."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

import saas.jobs.persistence_sync_progress as persistence_mod


@pytest.fixture
def tmp_engine(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE simulation_jobs ("
            " id INTEGER PRIMARY KEY,"
            " markets_config TEXT"
            ")"
        ))
        conn.execute(text("INSERT INTO simulation_jobs (id) VALUES (1)"))
        conn.commit()

    def _stub_engine():
        return engine

    monkeypatch.setattr(persistence_mod, "_get_sync_engine", _stub_engine)
    yield engine
    engine.dispose()


class TestUpdateMarketsConfigSync:
    def test_persists_markets_list_as_json(self, tmp_engine):
        markets = [{"question": "Will X?", "initial_price_yes": 0.6, "rationale": "because Y"}]
        persistence_mod._update_markets_config_sync(1, markets)
        with tmp_engine.connect() as conn:
            row = conn.execute(text("SELECT markets_config FROM simulation_jobs WHERE id=1")).first()
        assert json.loads(row[0]) == markets

    def test_none_becomes_sql_null(self, tmp_engine):
        persistence_mod._update_markets_config_sync(1, None)
        with tmp_engine.connect() as conn:
            row = conn.execute(text("SELECT markets_config FROM simulation_jobs WHERE id=1")).first()
        assert row[0] is None

    def test_missing_job_id_is_swallowed(self, tmp_engine, caplog):
        # Should not raise — mirrors the silent-fail pattern in _update_enrichment_sync.
        persistence_mod._update_markets_config_sync(9999, [{"question": "Q", "initial_price_yes": 0.5}])
```

- [ ] **Step 3: Run the test — expect FAIL**

Run: `pytest tests/jobs/test_markets_config_persistence.py -v`
Expected: `AttributeError: module 'saas.jobs.persistence_sync_progress' has no attribute '_update_markets_config_sync'`.

- [ ] **Step 4: Add the persistence helper**

Append to `saas/jobs/persistence_sync_progress.py` (after `_update_enrichment_sync`, around line 154):

```python
def _update_markets_config_sync(job_id: int, markets: list[dict] | None) -> None:
    """Persist derived markets_config to the SimulationJob row (sync, for Celery).

    markets=None clears the column. Matches the silent-fail pattern used by the
    other persistence helpers: any DB error logs a warning and returns.
    """
    import json as _json
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping markets_config save for job %d", job_id)
        return
    try:
        payload = _json.dumps(markets) if markets is not None else None
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET markets_config = :markets WHERE id = :job_id"),
                {"markets": payload, "job_id": job_id},
            )
            conn.commit()
            count = len(markets) if markets else 0
            logger.info("Saved markets_config for job %d (%d markets)", job_id, count)
    except Exception as exc:
        logger.warning("Could not save markets_config for job %d: %s", job_id, exc)
    finally:
        engine.dispose()
```

- [ ] **Step 5: Run the test — expect PASS**

Run: `pytest tests/jobs/test_markets_config_persistence.py -v`
Expected: 3 passed.

- [ ] **Step 6: Re-export in `persistence.py`**

Open `saas/jobs/persistence.py`. Find the imports block near line 38 that already pulls in `_update_enrichment_sync`. Add `_update_markets_config_sync` to the same import group. Then add the alias near line 52 (`_update_enrichment = _update_enrichment_sync`):

```python
_update_markets_config = _update_markets_config_sync
```

And add both names to the `__all__` list (around lines 148 and 162).

- [ ] **Step 7: Add the `markets_config` column to the model**

Open `saas/jobs/models.py`. The existing imports already include `JSON`. Append after the `resume_task_id` line (the last field, line 60):

```python
    markets_config: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 8: Create the Alembic migration**

Run: `head -5 alembic/versions/v3w4x5y6z7a8_add_reporting_status.py` to copy the format.

Create `alembic/versions/w4x5y6z7a8b9_add_markets_config.py`:

```python
"""add markets_config column to simulation_jobs

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-04-17

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_jobs",
        sa.Column("markets_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_jobs", "markets_config")
```

Verify `down_revision` matches the actual latest revision in the repo — don't take the ID above on faith, `grep -rn "revision = " alembic/versions/ | tail -3` and use whichever is the true head.

- [ ] **Step 9: Run the full engine suite to catch any broken tests**

Run: `pytest tests/ -x -q`
Expected: PASS (new column is nullable; no existing test should break).

- [ ] **Step 10: Commit**

```bash
git add saas/jobs/models.py saas/jobs/persistence_sync_progress.py saas/jobs/persistence.py alembic/versions/w4x5y6z7a8b9_add_markets_config.py tests/jobs/test_markets_config_persistence.py
git commit -m "$(cat <<'EOF'
feat(db): add markets_config column + persistence helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: LLM deriver module with stubbed-LLM tests

**Files:**
- Create: `saas/jobs/market_derivation.py`
- Create: `tests/jobs/test_market_derivation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/jobs/test_market_derivation.py`:

```python
"""Unit tests for saas.jobs.market_derivation."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from saas.jobs.market_derivation import (
    DERIVATION_SOURCE_FALLBACK,
    DERIVATION_SOURCE_LLM,
    derive_markets,
)


def _fake_grok_client(payload: dict | str):
    """Build a MagicMock emulating the OpenAI-compatible Grok client.

    The deriver calls ``client.responses.create(...)`` and reads
    ``response.output_text``. The payload is what the "LLM" returns.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    client = MagicMock()
    client.responses.create.return_value = MagicMock(output_text=text)
    return client


class TestDeriveMarkets:
    def test_happy_path_returns_validated_markets(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Fed cuts 50bp+?", "initial_price_yes": 0.45, "rationale": "labor market softening"},
                {"question": "Fed cuts 25bp?",   "initial_price_yes": 0.30, "rationale": "inflation still high"},
                {"question": "Fed holds rates?", "initial_price_yes": 0.25, "rationale": "base case"},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="Will the Fed cut rates?", enriched_seed="…", tier="small")
        assert out["source"] == DERIVATION_SOURCE_LLM
        assert len(out["markets"]) == 3
        assert out["markets"][0]["question"] == "Fed cuts 50bp+?"
        assert out["markets"][0]["rationale"] == "labor market softening"

    def test_tier_cap_slices(self, monkeypatch):
        markets = [{"question": f"Q{i}", "initial_price_yes": 0.5} for i in range(7)]
        client = _fake_grok_client({"markets": markets})
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        assert len(derive_markets("g", "s", "small")["markets"]) == 3
        assert len(derive_markets("g", "s", "medium")["markets"]) == 4
        assert len(derive_markets("g", "s", "large")["markets"]) == 5

    def test_initial_price_clamped(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Too high?", "initial_price_yes": 1.0},
                {"question": "Too low?",  "initial_price_yes": 0.0},
                {"question": "Just right?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        prices = [m["initial_price_yes"] for m in derive_markets("g", "s", "large")["markets"]]
        assert prices == [0.95, 0.05, 0.5]

    def test_duplicates_are_deduped_case_insensitive(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Will X happen?", "initial_price_yes": 0.5},
                {"question": "will x happen?", "initial_price_yes": 0.5},
                {"question": "Something else?", "initial_price_yes": 0.4},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert len(out) == 2
        assert out[0]["question"] == "Will X happen?"
        assert out[1]["question"] == "Something else?"

    def test_question_too_long_rejected(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "x" * 121, "initial_price_yes": 0.5},
                {"question": "Valid Q?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert len(out) == 1
        assert out[0]["question"] == "Valid Q?"

    def test_empty_question_rejected(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "   ", "initial_price_yes": 0.5},
                {"question": "Valid?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert [m["question"] for m in out] == ["Valid?"]

    def test_malformed_json_falls_back_to_single_market(self, monkeypatch):
        client = _fake_grok_client("this is not JSON")
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="My Goal?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
        assert out["markets"] == [{"question": "My Goal?", "initial_price_yes": 0.5, "rationale": ""}]

    def test_empty_markets_list_falls_back(self, monkeypatch):
        client = _fake_grok_client({"markets": []})
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="G?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK

    def test_missing_api_key_falls_back(self, monkeypatch):
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: None)
        out = derive_markets(goal="Goal text?", enriched_seed="", tier="medium")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
        assert out["markets"] == [{"question": "Goal text?", "initial_price_yes": 0.5, "rationale": ""}]

    def test_client_exception_falls_back(self, monkeypatch):
        client = MagicMock()
        client.responses.create.side_effect = RuntimeError("grok down")
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="G?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `pytest tests/jobs/test_market_derivation.py -v`
Expected: `ModuleNotFoundError: No module named 'saas.jobs.market_derivation'`.

- [ ] **Step 3: Implement the deriver**

Create `saas/jobs/market_derivation.py`:

```python
"""Derive prediction markets from a goal + enriched seed using xAI Grok.

Called from the Celery pipeline after enrichment, before the GPU pod provisions.
Output is persisted on SimulationJob.markets_config and forwarded to the pod so
the market env has markets to trade on.

Contract: always returns a non-empty list. Falls back to a single market built
from the goal itself if the LLM call fails, returns malformed JSON, or yields
zero valid markets after validation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DERIVATION_SOURCE_LLM = "llm"
DERIVATION_SOURCE_FALLBACK = "fallback_goal"

TIER_MARKET_CAPS = {"small": 3, "medium": 4, "large": 5}
_QUESTION_MAX_LEN = 120
_PRICE_MIN = 0.05
_PRICE_MAX = 0.95
_LLM_TIMEOUT_SECONDS = 20


def _build_client():
    """Return an OpenAI-compatible xAI client, or None if creds are missing.

    Mirrors the pattern in saas.jobs.enrichment.enrich_seed.
    """
    api_key = os.getenv("XAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    except Exception as exc:
        logger.warning("market_derivation: could not build xAI client: %s", exc)
        return None


def _build_prompt(goal: str, enriched_seed: str, cap: int) -> str:
    return (
        "You are a prediction market designer for an agent-based simulation.\n"
        f"Given a goal, derive up to {cap} binary (YES/NO) markets that collectively\n"
        "capture the resolution space of that goal. Markets should be:\n"
        "  - mutually informative (not trivially redundant)\n"
        "  - phrased with clear resolution criteria\n"
        "  - at most 120 characters per question\n\n"
        f"GOAL: {goal}\n\n"
        f"SEED CONTEXT:\n{enriched_seed[:3000]}\n\n"
        "Return ONLY a JSON object (no prose, no code fences) of this shape:\n"
        "{\n"
        '  "markets": [\n'
        '    {"question": "...", "initial_price_yes": 0.50, "rationale": "why this price"}\n'
        "  ]\n"
        "}\n"
        "initial_price_yes must be between 0.05 and 0.95 — do not use 0 or 1.\n"
    )


def _call_llm(goal: str, enriched_seed: str, cap: int) -> str | None:
    client = _build_client()
    if client is None:
        return None
    try:
        resp = client.responses.create(
            model="grok-4-fast-non-reasoning",
            input=_build_prompt(goal, enriched_seed, cap),
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        return resp.output_text or ""
    except Exception as exc:
        logger.warning("market_derivation: LLM call failed: %s", exc)
        return None


def _parse_raw(raw: str) -> list[dict[str, Any]] | None:
    """Extract the `markets` list from raw LLM output. Returns None on any parse issue."""
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    markets = data.get("markets")
    if not isinstance(markets, list):
        return None
    return markets


def _validate(raw_markets: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Validate + dedupe + tier-cap. Returns a possibly-empty list."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for m in raw_markets:
        if not isinstance(m, dict):
            continue
        q = m.get("question")
        if not isinstance(q, str):
            continue
        q = q.strip()
        if not q or len(q) > _QUESTION_MAX_LEN:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        price = m.get("initial_price_yes", 0.5)
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0.5
        price = max(_PRICE_MIN, min(_PRICE_MAX, price))
        rationale = m.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = ""
        out.append({
            "question": q,
            "initial_price_yes": price,
            "rationale": rationale.strip(),
        })
        if len(out) >= cap:
            break
    return out


def _fallback_from_goal(goal: str) -> list[dict[str, Any]]:
    q = (goal or "Will the simulated outcome occur?").strip()[:_QUESTION_MAX_LEN]
    return [{"question": q, "initial_price_yes": 0.5, "rationale": ""}]


def derive_markets(goal: str, enriched_seed: str, tier: str) -> dict[str, Any]:
    """Derive markets for a sim.

    Returns: {"markets": [...], "source": "llm" | "fallback_goal"}
    Always returns at least one market. Never raises.
    """
    cap = TIER_MARKET_CAPS.get(tier, TIER_MARKET_CAPS["small"])
    raw = _call_llm(goal, enriched_seed, cap)
    parsed = _parse_raw(raw or "")
    if parsed is None:
        logger.warning("markets.derivation_failed: unparseable or empty LLM output")
        return {"markets": _fallback_from_goal(goal), "source": DERIVATION_SOURCE_FALLBACK}
    markets = _validate(parsed, cap)
    if not markets:
        logger.warning("markets.derivation_failed: zero valid markets after validation")
        return {"markets": _fallback_from_goal(goal), "source": DERIVATION_SOURCE_FALLBACK}
    return {"markets": markets, "source": DERIVATION_SOURCE_LLM}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/jobs/test_market_derivation.py -v`
Expected: 10 passed.

- [ ] **Step 5: Run full jobs test dir to make sure nothing is broken**

Run: `pytest tests/jobs/ -x -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/market_derivation.py tests/jobs/test_market_derivation.py
git commit -m "$(cat <<'EOF'
feat(markets): LLM-based prediction-market derivation from goal

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `markets_config` to `JobConfig` + pod-handoff payload

**Files:**
- Modify: `saas/jobs/config.py:23-41` (add field)
- Modify: `saas/jobs/pipeline.py:88-115` (include in POST body)
- Modify existing test (if any) for pipeline.submit_job, OR create: `tests/jobs/test_pipeline_submit_job.py`

- [ ] **Step 1: Check if there's already a test for submit_job**

Run: `grep -rn "submit_job" tests/ 2>&1 | grep -v __pycache__`

If a test exists, extend it in Step 2. Otherwise create the new test file.

- [ ] **Step 2: Write the failing test**

Either add to the existing `tests/jobs/test_pipeline*.py`, or create `tests/jobs/test_pipeline_submit_job.py`:

```python
"""Tests for pipeline.submit_job payload shape."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.jobs.config import JobConfig
from saas.jobs.pipeline import submit_job


def _make_config(**overrides):
    base = dict(
        job_id=1, user_id="u1", seed_text="s", goal="g", tier="small",
        model_id="m", gpu_type="L40S", max_rounds=15, vllm_args="",
        llm_api_key="", openai_api_key="",
        neo4j_uri="", neo4j_user="", neo4j_password="",
        forecast_days=30, target_agents=5, upload_urls={"x": "y"},
    )
    base.update(overrides)
    return JobConfig(**base)


class TestSubmitJobPayload:
    @pytest.mark.asyncio
    async def test_markets_config_included_when_set(self):
        client = MagicMock()
        resp = MagicMock(status_code=200)
        client.post = AsyncMock(return_value=resp)
        cfg = _make_config(markets_config=[
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": ""},
        ])
        await submit_job("http://worker", cfg, client)
        called_kwargs = client.post.call_args.kwargs
        body = called_kwargs["json"]
        assert body["markets_config"] == [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": ""},
        ]

    @pytest.mark.asyncio
    async def test_markets_config_none_when_unset(self):
        client = MagicMock()
        resp = MagicMock(status_code=200)
        client.post = AsyncMock(return_value=resp)
        cfg = _make_config()
        await submit_job("http://worker", cfg, client)
        body = client.post.call_args.kwargs["json"]
        assert body["markets_config"] is None
```

- [ ] **Step 3: Run the test — expect FAIL**

Run: `pytest tests/jobs/test_pipeline_submit_job.py -v`
Expected: `TypeError: JobConfig.__init__() got an unexpected keyword argument 'markets_config'` (from `_make_config`).

- [ ] **Step 4: Add the field to JobConfig**

In `saas/jobs/config.py`, append after the `upload_urls` line (around line 41):

```python
    markets_config: list[dict] | None = None
```

- [ ] **Step 5: Add the key to the submit_job POST body**

In `saas/jobs/pipeline.py::submit_job` (line 94), extend the `json=` dict. Before:

```python
    resp = await client.post(f"{worker_url}/job", json={
        "seed_text": config.seed_text,
        "goal": config.goal,
        "max_rounds": config.max_rounds,
        "forecast_days": config.forecast_days,
        "target_agents": config.target_agents,
        "upload_urls": config.upload_urls,
    }, timeout=30)
```

After:

```python
    resp = await client.post(f"{worker_url}/job", json={
        "seed_text": config.seed_text,
        "goal": config.goal,
        "max_rounds": config.max_rounds,
        "forecast_days": config.forecast_days,
        "target_agents": config.target_agents,
        "upload_urls": config.upload_urls,
        "markets_config": config.markets_config,
    }, timeout=30)
```

- [ ] **Step 6: Run the test — expect PASS**

Run: `pytest tests/jobs/test_pipeline_submit_job.py -v`
Expected: 2 passed.

- [ ] **Step 7: Run the broader pipeline tests to make sure nothing else cares about the payload shape**

Run: `pytest tests/jobs/ -x -q`
Expected: PASS. If anything breaks because a test asserts the exact key set of the POST body, add `markets_config: None` to its expected dict.

- [ ] **Step 8: Commit**

```bash
git add saas/jobs/config.py saas/jobs/pipeline.py tests/jobs/test_pipeline_submit_job.py
git commit -m "$(cat <<'EOF'
feat(pipeline): carry markets_config through JobConfig → pod submit payload

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Wire the deriver into `run_simulation_task`

**Files:**
- Modify: `saas/jobs/tasks.py` (imports + call site)
- Create OR extend: `tests/jobs/test_run_simulation_task_markets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/jobs/test_run_simulation_task_markets.py`:

```python
"""Tests that run_simulation_task calls derive_markets and persists the result."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# NB: this test stubs the whole GPU pipeline — we only care that (a) the deriver
# is called, (b) its output is persisted via _update_markets_config, and (c) the
# JobConfig handed to JobRunner.run carries markets_config.


class TestRunSimulationTaskDeriver:
    def test_derive_called_after_enrichment_and_persisted(self, monkeypatch):
        # Patch everything the Celery task depends on so the test is pure-logic.
        from saas.jobs import tasks as tasks_mod

        captured = {}

        def fake_derive(goal, enriched_seed, tier):
            captured["derive_args"] = (goal, enriched_seed, tier)
            return {
                "markets": [{"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"}],
                "source": "llm",
            }

        def fake_update_markets(job_id, markets):
            captured["persisted"] = (job_id, markets)

        class FakeRunner:
            def __init__(self, *a, **k): pass
            async def run(self, config):
                captured["config_markets"] = config.markets_config
                return {"pod_id": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
                        "sim_data_uploaded": True, "report": ""}

        def fake_run_async(coro):
            import asyncio
            return asyncio.get_event_loop().run_until_complete(coro)

        monkeypatch.setattr(tasks_mod, "_get_gpu_provider", lambda: MagicMock())
        monkeypatch.setattr(tasks_mod, "JobRunner", FakeRunner)
        monkeypatch.setattr(tasks_mod, "_run_async", fake_run_async)
        monkeypatch.setattr(tasks_mod, "_update_markets_config", fake_update_markets)
        monkeypatch.setattr(tasks_mod, "_save_job_results", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_update_job_metadata", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_mark_job_failed", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_update_enrichment", lambda *a, **k: None)

        # Bypass the enrichment branch: patch enrich_seed so seed stays raw.
        import saas.jobs.enrichment as enrichment_mod
        monkeypatch.setattr(enrichment_mod, "enrich_seed", lambda s, g: None)

        # Patch the deriver where tasks.py imports it from.
        monkeypatch.setattr("saas.jobs.market_derivation.derive_markets", fake_derive)

        # Call the task's *run* function directly (bypass Celery)
        tasks_mod.run_simulation_task.run(
            job_id=42, user_id="u1",
            seed_text="seed", goal="Will X?", tier="small",
            model_id="m", gpu_type="L40S", max_rounds=15,
            vllm_args="", llm_api_key="",
            enrich_web=False,  # skip enrichment to keep test narrow
        )

        assert captured["derive_args"] == ("Will X?", "seed", "small")
        assert captured["persisted"] == (42, [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"},
        ])
        assert captured["config_markets"] == [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"},
        ]
```

This test is inherently invasive of `tasks.py` internals. If it proves too fragile (e.g., the Celery `.run()` bypass doesn't work cleanly in this repo's test setup), drop it to a simpler assertion: patch `derive_markets` at the module level and assert it was called once with the expected args, without driving the full task body. Keep the spirit: prove derive → persist → JobConfig.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/jobs/test_run_simulation_task_markets.py -v`
Expected: FAIL (the wiring doesn't exist yet). Likely error: `AttributeError` on `tasks_mod._update_markets_config` or `KeyError` on captured keys.

- [ ] **Step 3: Wire in the deriver**

Open `saas/jobs/tasks.py`. In the imports block near line 16 (next to `_update_enrichment`), add `_update_markets_config`:

```python
from saas.jobs.persistence import (
    _update_pipeline_stage_sync,
    ...
    _update_enrichment,
    _update_markets_config,
)
```

(Use the real existing import shape — the file already imports from `saas.jobs.persistence`, just append `_update_markets_config` to that group.)

Then, inside `run_simulation_task`, immediately AFTER the enrichment branch (after line 83) and BEFORE the `JobConfig(...)` construction, insert:

```python
    # --- Market derivation -------------------------------------------------
    # Derive 3–5 prediction markets from the (possibly enriched) seed + goal.
    # Fails soft: always returns at least one market.
    from saas.jobs.market_derivation import derive_markets
    derivation = derive_markets(
        goal=goal, enriched_seed=enriched_seed_text, tier=tier,
    )
    markets_config = derivation["markets"]
    logger.info(
        "job.markets_derived job_id=%d source=%s count=%d",
        job_id, derivation["source"], len(markets_config),
    )
    _update_markets_config(job_id, markets_config)
```

Then add `markets_config=markets_config` to the `JobConfig(...)` call (around line 85, immediately below `upload_urls=upload_urls,`).

- [ ] **Step 4: Run the test — expect PASS**

Run: `pytest tests/jobs/test_run_simulation_task_markets.py -v`
Expected: PASS. If it fails because the test's Celery `.run()` bypass didn't fire correctly, relax the test to the narrower version described at the end of Step 1.

- [ ] **Step 5: Run the full jobs + engine suites**

Run: `pytest tests/ -x -q`
Expected: PASS. If an existing `run_simulation_task` test breaks because the deriver now gets called unexpectedly, add `monkeypatch.setattr("saas.jobs.market_derivation.derive_markets", lambda *a, **k: {"markets": [...], "source": "fallback_goal"})` to that test's fixtures.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/tasks.py tests/jobs/test_run_simulation_task_markets.py
git commit -m "$(cat <<'EOF'
feat(tasks): call derive_markets after enrichment, persist, forward to pod

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Pod-side plumbing — worker_api writes markets file + CLI arg

**Files:**
- Modify: `infra/docker/worker_api.py:178-204` (`/job` handler) + `_run_pipeline`
- Modify: `infra/docker/run_job_v2.py:51-108` (add CLI arg + wire into run_pipeline)
- Modify: `infra/docker/run_job_v2_runner.py:63-95` (`run_simulation` accepts `markets_config`)
- Modify: existing `tests/engine/test_run_job_v2*.py` (add markets_config path coverage)

- [ ] **Step 1: Write the failing test — runner plumbs markets into MarketConfig**

Check existing `tests/engine/test_run_job_v2.py` for its test pattern. Add a new test to that file:

```python
class TestMarketsConfigPlumbing:
    @pytest.mark.asyncio
    async def test_run_simulation_passes_markets_to_env(self, monkeypatch):
        """run_simulation must pass markets_config into EnvironmentConfig(type='market')."""
        from infra.docker.run_job_v2_runner import run_simulation
        from simswarm.types import Entity

        captured = {}

        class FakeEngine:
            def __init__(self, **kw): pass
            async def run(self, config, on_progress=None):
                # Pull out the market env config
                market_ec = next(ec for ec in config.environments if ec.type == "market")
                captured["market_params"] = market_ec.params
                class Result:
                    chat_log = []
                    graph_data = type("G", (), {"nodes": [], "edges": [], "metadata": {}})()
                    trajectories = {}
                return Result()

        monkeypatch.setattr("infra.docker.run_job_v2_runner.Engine", FakeEngine)

        # Stub the LLM clients + relations + personas so the fn doesn't hit network
        monkeypatch.setattr("infra.docker.run_job_v2_runner.LLMClient",
                            lambda *a, **k: type("X", (), {"close": lambda self: None})())
        monkeypatch.setattr("infra.docker.run_job_v2_runner.extract_relations",
                            lambda *a, **k: [])
        monkeypatch.setattr("infra.docker.run_job_v2_runner.enrich_profiles_with_personas",
                            lambda profiles, *a, **k: profiles)

        entity = Entity(id="a", name="A", type="person", summary="x")
        markets = [{"question": "Will X?", "initial_price_yes": 0.55}]

        await run_simulation(
            seed_text="", goal="", max_rounds=1, entities=[entity], target_agents=1,
            markets_config=markets,
        )

        assert captured["market_params"]["markets"] == markets
```

If the test file is async-unfriendly, use `asyncio.run(...)` inside a sync test and drop `@pytest.mark.asyncio`.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/engine/test_run_job_v2.py::TestMarketsConfigPlumbing -v`
Expected: FAIL — `TypeError: run_simulation() got an unexpected keyword argument 'markets_config'`.

- [ ] **Step 3: Extend `run_simulation` in run_job_v2_runner.py**

Open `infra/docker/run_job_v2_runner.py`. Update the `run_simulation` signature (line 63) and the `SimulationConfig(...)` body (lines 74-84). Before:

```python
async def run_simulation(
    seed_text: str,
    goal: str,
    max_rounds: int,
    entities: list[Entity],
    target_agents: int,
) -> SimulationResult:
    ...
    config = SimulationConfig(
        ...
        environments=[
            EnvironmentConfig(type="social", params={}),
            EnvironmentConfig(type="market", params={}),
        ],
        ...
    )
```

After:

```python
async def run_simulation(
    seed_text: str,
    goal: str,
    max_rounds: int,
    entities: list[Entity],
    target_agents: int,
    markets_config: list[dict] | None = None,
) -> SimulationResult:
    ...
    # Seed the market env with derived markets so agents actually have
    # something to trade on. Fall back to a goal-derived single market if
    # upstream derivation produced nothing (shouldn't happen post-T4 but we
    # keep the belt-and-suspenders).
    market_entries = [
        {"question": m["question"],
         "initial_price_yes": m.get("initial_price_yes", 0.5)}
        for m in (markets_config or [])
    ] or [{"question": goal or "Will the simulated outcome occur?",
           "initial_price_yes": 0.5}]

    config = SimulationConfig(
        ...
        environments=[
            EnvironmentConfig(type="social", params={}),
            EnvironmentConfig(type="market", params={"markets": market_entries}),
        ],
        ...
    )
```

- [ ] **Step 4: Run the runner test — expect PASS**

Run: `pytest tests/engine/test_run_job_v2.py::TestMarketsConfigPlumbing -v`
Expected: PASS.

- [ ] **Step 5: Extend `run_pipeline` CLI in run_job_v2.py**

Open `infra/docker/run_job_v2.py`. Update `run_pipeline` signature and body (lines 51-80), and `main` (lines 87-104).

`run_pipeline` before:

```python
def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
) -> dict:
    ...
    result = asyncio.run(
        run_simulation(seed_text, goal, max_rounds, entities, target_agents)
    )
```

After:

```python
def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
    markets_config: list[dict] | None = None,
) -> dict:
    ...
    result = asyncio.run(
        run_simulation(
            seed_text, goal, max_rounds, entities, target_agents,
            markets_config=markets_config,
        )
    )
```

`main` — add the CLI arg and load the file:

```python
def main() -> None:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--output-dir", default="/tmp/results")
    parser.add_argument("--target-agents", type=int, default=5)
    parser.add_argument("--markets-config-file",
                        help="JSON file with a list of {question, initial_price_yes, rationale}")
    parser.add_argument("--skip-vllm-wait", action="store_true")
    args = parser.parse_args()

    seed_text = Path(args.seed_file).read_text(encoding="utf-8")

    markets_config = None
    if args.markets_config_file:
        markets_config = json.loads(Path(args.markets_config_file).read_text(encoding="utf-8"))

    if not args.skip_vllm_wait and _SERVICE_INIT_AVAILABLE:
        wait_for_neo4j()

    run_pipeline(
        seed_text, args.goal, args.max_rounds, args.output_dir,
        args.target_agents, markets_config=markets_config,
    )
```

- [ ] **Step 6: Extend worker_api.py — accept field, write file, pass CLI arg**

Open `infra/docker/worker_api.py`.

**(a)** In `submit_job` (line 178), extract `markets_config`:

```python
def submit_job():
    data = request.json or {}
    seed_text = data.get("seed_text", "")
    goal = data.get("goal", "")
    max_rounds = data.get("max_rounds", 200)
    forecast_days = data.get("forecast_days")
    upload_urls = data.get("upload_urls")
    target_agents = data.get("target_agents", 5)
    markets_config = data.get("markets_config")  # NEW
    ...
    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds, forecast_days, upload_urls, target_agents, markets_config),
        daemon=True,
    )
    thread.start()
```

**(b)** In `_run_pipeline` (line 86), add the new positional arg, write the file, and extend the subprocess argv:

```python
def _run_pipeline(seed_text, goal, max_rounds, forecast_days=None, upload_urls=None,
                  target_agents=5, markets_config=None):
    try:
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        extra_args = []
        if markets_config is not None:
            markets_file = Path("/tmp/markets.json")
            markets_file.write_text(json.dumps(markets_config))
            extra_args = ["--markets-config-file", str(markets_file)]

        LOG_FILE.write_text("")

        with open(LOG_FILE, "w") as log_fh:
            proc = subprocess.Popen(
                [
                    "python3", "-u", "/app/run_job_v2.py",
                    "--seed-file", str(seed_file),
                    "--goal", goal,
                    "--max-rounds", str(max_rounds),
                    "--target-agents", str(target_agents),
                    "--output-dir", "/tmp/results",
                    *extra_args,
                ],
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env={**os.environ},
            )
            proc.wait(timeout=3600)
```

Check that `json` is already imported at the top of `worker_api.py`. If not, add `import json` with the other imports.

- [ ] **Step 7: Run the full engine + jobs suites**

Run: `pytest tests/ -x -q`
Expected: PASS. If any test directly asserts the run_job_v2 CLI argv shape, update it to include the new (optional) arg.

- [ ] **Step 8: Commit**

```bash
git add infra/docker/run_job_v2.py infra/docker/run_job_v2_runner.py infra/docker/worker_api.py tests/engine/test_run_job_v2.py
git commit -m "$(cat <<'EOF'
feat(pod): seed market env with markets_config from SaaS handoff

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: API schema — expose `markets_config` on GET /jobs/{id}

**Files:**
- Modify: `saas/jobs/schemas.py::JobResponse` (around lines 57-79)
- Create or extend: `tests/test_jobs_api.py` (or equivalent — find via `grep -rn "JobResponse" tests/`)

- [ ] **Step 1: Locate existing job API tests**

Run: `grep -rn "markets_config\|JobResponse\|get.*jobs.*id" tests/ 2>&1 | grep -v __pycache__ | head -10`

Pick the test file that covers GET /jobs/{id}. Typically `tests/test_jobs_api.py` or `tests/test_jobs_endpoints.py`.

- [ ] **Step 2: Write the failing test**

Add to the appropriate test file:

```python
class TestJobResponseMarketsConfig:
    async def test_get_job_returns_markets_config(self, client, funded_user, db_session):
        from saas.jobs.models import SimulationJob, JobStatus
        from datetime import datetime, timezone

        markets = [
            {"question": "Will X?", "initial_price_yes": 0.55, "rationale": "because"}
        ]
        job = SimulationJob(
            user_id=funded_user["user_id"],
            seed_text="s", goal="g", tier="small",
            credits_charged=30, status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            markets_config=markets,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.get(
            f"/api/jobs/{job.id}",
            headers={"Authorization": f"Bearer {funded_user['token']}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["markets_config"] == markets

    async def test_get_job_markets_config_null_when_unset(self, client, funded_user, db_session):
        from saas.jobs.models import SimulationJob, JobStatus
        from datetime import datetime, timezone

        job = SimulationJob(
            user_id=funded_user["user_id"],
            seed_text="s", goal="g", tier="small",
            credits_charged=30, status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.get(
            f"/api/jobs/{job.id}",
            headers={"Authorization": f"Bearer {funded_user['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["markets_config"] is None
```

If the fixture names in `tests/conftest.py` differ (e.g. `auth_headers` instead of `funded_user`), adapt to the local convention — `grep -n "def funded_user\|def auth_headers\|def client" tests/conftest.py`.

- [ ] **Step 3: Run — expect FAIL**

Expected: `KeyError: 'markets_config'` in the response body.

- [ ] **Step 4: Add the field to the schema**

Open `saas/jobs/schemas.py`. In `JobResponse` (line 57), add after `live_status`:

```python
    markets_config: list[dict] | None = None
```

- [ ] **Step 5: Run — expect PASS**

Expected: both new tests pass.

- [ ] **Step 6: Full suite sanity run**

Run: `pytest tests/ -x -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add saas/jobs/schemas.py tests/test_jobs_api.py
git commit -m "$(cat <<'EOF'
feat(api): expose markets_config on GET /jobs/{id}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — `MarketsList.vue` component + wiring

**Files:**
- Create: `frontend/src/components/data/MarketsList.vue`
- Create: `frontend/src/components/data/__tests__/MarketsList.spec.js`
- Modify: `frontend/src/components/data/DataDashboard.vue` (add prop + render)
- Modify: `frontend/src/views/SimulationResults.vue:99` (pass prop through)

- [ ] **Step 1: Write the failing Vitest test**

Create `frontend/src/components/data/__tests__/MarketsList.spec.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MarketsList from '../MarketsList.vue'

describe('MarketsList', () => {
  it('renders a row per market with question + price + rationale', () => {
    const markets = [
      { question: 'Fed cuts 50bp+?', initial_price_yes: 0.45, rationale: 'labor market softening' },
      { question: 'Fed holds rates?', initial_price_yes: 0.25, rationale: 'base case' },
    ]
    const wrapper = mount(MarketsList, { props: { markets } })
    const rows = wrapper.findAll('[data-test="market-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Fed cuts 50bp+?')
    expect(rows[0].text()).toContain('45%')
    expect(rows[0].text()).toContain('labor market softening')
  })

  it('shows empty state when no markets', () => {
    const wrapper = mount(MarketsList, { props: { markets: [] } })
    expect(wrapper.text().toLowerCase()).toContain('no markets')
  })

  it('omits rationale cleanly when blank', () => {
    const wrapper = mount(MarketsList, {
      props: { markets: [{ question: 'Q?', initial_price_yes: 0.5, rationale: '' }] },
    })
    expect(wrapper.findAll('[data-test="market-rationale"]')).toHaveLength(0)
  })

  it('handles null markets prop as empty', () => {
    const wrapper = mount(MarketsList, { props: { markets: null } })
    expect(wrapper.findAll('[data-test="market-row"]')).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && npm test -- --run src/components/data/__tests__/MarketsList.spec.js`
Expected: FAIL — file not found.

- [ ] **Step 3: Build `MarketsList.vue`**

Create `frontend/src/components/data/MarketsList.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">
      Prediction Markets
    </div>
    <div v-if="rows.length" class="space-y-2">
      <div v-for="(m, idx) in rows" :key="idx"
           data-test="market-row"
           class="flex flex-col gap-1 p-3 rounded-lg bg-ocean-abyss/40 border border-mist-depth/60">
        <div class="flex items-baseline justify-between gap-3">
          <span class="text-sm text-ocean-cyan truncate">{{ m.question }}</span>
          <span class="text-xs font-mono text-mist-slate">
            YES {{ Math.round((m.initial_price_yes ?? 0.5) * 100) }}%
          </span>
        </div>
        <div v-if="m.rationale" data-test="market-rationale"
             class="text-xs text-mist-drift leading-relaxed">
          {{ m.rationale }}
        </div>
      </div>
    </div>
    <div v-else class="text-xs text-mist-slate text-center py-6">
      No markets for this simulation.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  markets: { type: Array, default: () => [] },
})

const rows = computed(() => Array.isArray(props.markets) ? props.markets : [])
</script>
```

- [ ] **Step 4: Run the vitest — expect PASS**

Run: `cd frontend && npm test -- --run src/components/data/__tests__/MarketsList.spec.js`
Expected: 4 passed.

- [ ] **Step 5: Wire into DataDashboard**

Open `frontend/src/components/data/DataDashboard.vue`. Add the import near line 39:

```javascript
import MarketsList from './MarketsList.vue'
```

Add a prop in the `defineProps` call (line 42). Before:

```javascript
const props = defineProps({
  jobId: { type: [String, Number], required: true },
})
```

After:

```javascript
const props = defineProps({
  jobId: { type: [String, Number], required: true },
  markets: { type: Array, default: () => [] },
})
```

Render it in the template grid, immediately above the `<TradeFeed>` block (around line 19-21):

```vue
<div class="md:col-span-2">
  <MarketsList :markets="markets" />
</div>
<div class="md:col-span-2">
  <TradeFeed :trades="trades" />
</div>
```

- [ ] **Step 6: Wire the prop from SimulationResults**

Open `frontend/src/views/SimulationResults.vue`. Find line 99 (`<DataDashboard :jobId="jobId" />`) and change to:

```vue
<DataDashboard :jobId="jobId" :markets="job?.markets_config || []" />
```

The `job` ref is already populated by `job.value = await getJob(jobId)` at line 245.

- [ ] **Step 7: Run the full frontend vitest suite**

Run: `cd frontend && npm test -- --run`
Expected: PASS — all existing tests + the new MarketsList spec. If `DataDashboard.spec.js` was asserting a specific child-component set, update it to allow MarketsList.

- [ ] **Step 8: Manual smoke in dev (optional but recommended)**

Run the dev servers in parallel:
- Terminal 1: `uvicorn saas.main:create_app --factory --reload --port 8080`
- Terminal 2: `cd frontend && npm run dev`

Load an existing completed job in the browser. Because `markets_config` is NULL on pre-Task-4 jobs, the panel should show "No markets for this simulation." That's correct behavior.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/data/MarketsList.vue frontend/src/components/data/__tests__/MarketsList.spec.js frontend/src/components/data/DataDashboard.vue frontend/src/views/SimulationResults.vue
git commit -m "$(cat <<'EOF'
feat(frontend): show derived prediction markets in data dashboard

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: End-to-end integration test

**Files:**
- Create: `tests/test_markets_integration.py`

Goal: prove the whole chain (deriver → persist → JobConfig → pod handoff → MarketConfig) by stubbing only the external LLM + GPU. Everything between runs real code.

- [ ] **Step 1: Write the integration test**

```python
"""End-to-end integration: deriver output flows into MarketConfig."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


class TestMarketsEndToEnd:
    @pytest.mark.asyncio
    async def test_derived_markets_reach_market_env(self, monkeypatch, tmp_path):
        # 1. Stub the LLM deriver
        monkeypatch.setattr(
            "saas.jobs.market_derivation._build_client",
            lambda: _make_fake_grok([
                {"question": "Will it rain?", "initial_price_yes": 0.6, "rationale": "r1"},
                {"question": "Will it snow?", "initial_price_yes": 0.2, "rationale": "r2"},
            ]),
        )

        from saas.jobs.market_derivation import derive_markets
        derivation = derive_markets(goal="Weather?", enriched_seed="", tier="small")

        # 2. Prove the pod runner accepts + plumbs the list
        from infra.docker.run_job_v2_runner import run_simulation
        from simswarm.types import Entity

        captured = {}

        class FakeEngine:
            def __init__(self, **kw): pass
            async def run(self, config, on_progress=None):
                market_ec = next(ec for ec in config.environments if ec.type == "market")
                captured["market_params"] = market_ec.params
                class R:
                    chat_log = []
                    graph_data = type("G", (), {"nodes": [], "edges": [], "metadata": {}})()
                    trajectories = {}
                return R()

        monkeypatch.setattr("infra.docker.run_job_v2_runner.Engine", FakeEngine)
        monkeypatch.setattr("infra.docker.run_job_v2_runner.LLMClient",
                            lambda *a, **k: type("X", (), {"close": lambda self: None})())
        monkeypatch.setattr("infra.docker.run_job_v2_runner.extract_relations",
                            lambda *a, **k: [])
        monkeypatch.setattr("infra.docker.run_job_v2_runner.enrich_profiles_with_personas",
                            lambda p, *a, **k: p)

        await run_simulation(
            seed_text="", goal="Weather?", max_rounds=1,
            entities=[Entity(id="a", name="A", type="person", summary="x")],
            target_agents=1,
            markets_config=derivation["markets"],
        )

        assert captured["market_params"]["markets"] == [
            {"question": "Will it rain?", "initial_price_yes": 0.6},
            {"question": "Will it snow?", "initial_price_yes": 0.2},
        ]


def _make_fake_grok(markets):
    client = MagicMock()
    client.responses.create.return_value = MagicMock(
        output_text=json.dumps({"markets": markets})
    )
    return client
```

- [ ] **Step 2: Run — expect PASS**

Run: `pytest tests/test_markets_integration.py -v`
Expected: PASS (all pieces already implemented in Tasks 2 + 5).

- [ ] **Step 3: Commit**

```bash
git add tests/test_markets_integration.py
git commit -m "$(cat <<'EOF'
test: end-to-end integration of markets derivation → env config

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Prod smoke test

**Files:** none — operational.

- [ ] **Step 1: Merge and deploy**

Push the branch to `main` (triggers GitHub Actions: Build Worker Image → Deploy to Hetzner). Wait for the Deploy workflow to complete successfully.

- [ ] **Step 2: Run migration on the live DB**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose run --rm migrate"
```

Verify the new column exists:

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose exec -T db psql -U fishcloud -d fishcloud \
   -c \"SELECT column_name FROM information_schema.columns WHERE table_name='simulation_jobs' AND column_name='markets_config';\""
```

Expected: one row.

- [ ] **Step 3: Kick off a small sim**

```bash
TOKEN=$(curl -s -X POST https://simswarm.xyz/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$SIMSWARM_TEST_EMAIL\",\"password\":\"$SIMSWARM_TEST_PASSWORD\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s -X POST https://simswarm.xyz/api/jobs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "seed_text": "The Federal Reserve faces pressure from softening labor data while inflation persists above target. Markets debate whether a 50bp cut arrives at the next FOMC.",
    "goal": "Will the Fed cut by 50 basis points at the next meeting?",
    "tier": "small", "enrich_web": true, "forecast_days": 30
  }'
```

Note the returned `id`.

- [ ] **Step 4: Verify markets_config on the job row**

Wait until status > PROVISIONING, then:

```bash
curl -s https://simswarm.xyz/api/jobs/<ID> -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['markets_config'], indent=2))"
```

Expected: list of 3 markets with `question`, `initial_price_yes`, `rationale`. None empty.

- [ ] **Step 5: Wait for completion, verify trades.json**

Once status is COMPLETED (~20–48 min):

```bash
FILES=$(curl -s "https://simswarm.xyz/api/jobs/<ID>/sim-data" -H "Authorization: Bearer $TOKEN")
URL=$(echo "$FILES" | python3 -c 'import sys,json;print(json.load(sys.stdin)["files"]["trades.json"])')
curl -s "$URL" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'total: {len(d)}')
if d:
  print(f'successes: {sum(1 for t in d if t.get(\"success\"))}/{len(d)}')
  print('sample:', json.dumps(d[0], indent=2))
"
```

Expected:
- total > 0
- at least some entries with `success=True`
- sample entry has non-null `cost`, `price`, `side`, `outcome`.

- [ ] **Step 6: Check the UI**

Open `https://simswarm.xyz/simulation/<ID>` in a browser. Verify:
- **Prediction Markets** panel shows the 3 derived questions with percentages and rationale blurbs.
- **Trades** panel shows real `$NN` and `NN%` — no `NaN`.
- Mix of **BUY** and **SELL** labels (not all one side).

- [ ] **Step 7: If everything renders, you're done**

If anything regresses, capture the job ID, the failing panel's screenshot, and the trades.json contents, then open a follow-up bug with that evidence. Don't patch blindly.

---

## Self-Review Checklist (for plan author)

- [x] **Spec coverage:** Every section of the spec maps to at least one task.
  - *DB column* → Task 1.
  - *Deriver module with validation/fallback/tier caps* → Task 2.
  - *Celery wiring* → Task 4 (with persistence helper from Task 1).
  - *SaaS → pod handoff* → Tasks 3 + 5.
  - *UI surface with rationale in v1* → Tasks 6 + 7.
  - *Failure modes* → covered in Task 2 tests (malformed JSON, client exception, missing API key, empty list, tier cap, clamp, dedupe).
- [x] **Placeholder scan:** No TBDs or "similar to Task N" shortcuts. Every code block is complete.
- [x] **Type consistency:** `markets_config` is used uniformly across Python (list[dict] | None) and JSON. `derive_markets` returns `{"markets": [...], "source": "llm"|"fallback_goal"}` consistently. The `_update_markets_config` persistence helper takes `list[dict] | None`.
- [x] **Dependency order:** Task 1 adds the column before Task 4 writes to it; Task 3 adds the JobConfig field before Task 5 reads it on the pod side; Task 6 API surface lands before Task 7 frontend consumes it; Task 8 integration test runs after everything else.
- [x] **Commit granularity:** Each task is 1 commit. 9 commits total (Task 9 is operational — no code commit).

## Rollout notes

- **Backwards compat:** Jobs created before the migration have `markets_config=NULL`. The pod falls back to `{question: goal, initial_price_yes: 0.5}` in that case (run_job_v2_runner logic), so nothing breaks if the migration somehow hasn't run yet on a worker that hits an old record. The UI renders "No markets for this simulation." cleanly.
- **Cost per sim:** +~\$0.01–0.03 (Grok call). Trivial vs. the GPU cost.
- **No API contract break:** The new `markets_config` field on `JobResponse` is additive and nullable; existing clients ignore it.
- **Migration safety:** adding a nullable JSON column on Postgres 16 is a metadata-only change — no table rewrite, no blocking.

## Out of scope (explicitly)

- Removing the `enrich_web` toggle (separate work, referenced in the spec).
- Wizard-time market preview / editing.
- Market resolution at sim end.
- Cross-sim market continuity / "fork sim".
- Persona-to-market bias wiring.
