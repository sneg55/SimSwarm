# Simulation Timing Retune — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make simulations complete within their tier timeout now that tool calling works (rounds take ~5 min instead of <1s when tool calls were broken).

**Architecture:** Two fixes: (1) Change `max_rounds` semantics from ceiling to target — the engine currently computes `min(config_rounds, max_rounds)` which always picks the config's lower value; we make it always use `max_rounds` when provided. (2) Retune tier parameters via Alembic migration — reduce `max_rounds` to fit the timeout budget given ~5 min/round throughput, and lower `max-model-len` from 32768→8192 to quadruple vLLM concurrency.

**Tech Stack:** Alembic, PostgreSQL, Python (MiroShark engine)

---

### Timing Budget

With tool calling active on L40S + Qwen3-14B:
- ~30 LLM calls/round (10 agents × 3 platforms)
- vLLM concurrency at 32K ctx: ~3-4 seqs → ~8 batches × 25s = 200s
- vLLM concurrency at 8K ctx: ~12-16 seqs → ~2 batches × 25s = 50s
- Per-round overhead (rec_table, beliefs, memory): ~30s

| Tier | Timeout | Budget/round (8K ctx) | Max rounds | Target |
|------|---------|----------------------|------------|--------|
| small | 2700s (45m) | ~80s | **25** | ~33 min |
| medium | 18000s (5h) | ~80s | **100** | ~2.2h |
| large | 43200s (12h) | ~80s | **200** | ~4.4h |

---

### Task 1: Fix max_rounds semantics in engine — use as target, not ceiling

**Files:**
- Modify: `vendor/miroshark/backend/app/services/simulation_runner.py:370-380`
- Modify: `vendor/miroshark/backend/scripts/sim_twitter_runner.py:120-127`

The engine computes `total_rounds = total_hours * 60 / minutes_per_round` (=72 from config), then caps with `min(total_rounds, max_rounds)`. Since config always gives 72 and SaaS sends 100, `min(72,100)=72` — the SaaS value is ignored. Fix: when `max_rounds` is provided, use it directly.

- [ ] **Step 1: Fix simulation_runner.py — use max_rounds as override, not cap**

In `vendor/miroshark/backend/app/services/simulation_runner.py`, replace lines 370-380:

```python
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # If max rounds specified, truncate
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"Rounds truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
```

with:

```python
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)

        # max_rounds from SaaS overrides config-derived round count
        if max_rounds is not None and max_rounds > 0:
            total_rounds = max_rounds
            logger.info(f"Using SaaS max_rounds={max_rounds} (config default would be {int(total_hours * 60 / minutes_per_round)})")
        else:
            total_rounds = int(total_hours * 60 / minutes_per_round)
```

- [ ] **Step 2: Verify sim_twitter_runner.py already handles this correctly**

Read `vendor/miroshark/backend/scripts/sim_twitter_runner.py:120-127` — this code already does:
```python
if max_rounds is not None and max_rounds > 0:
    total_rounds = max_rounds
```
This is correct (override, not cap). No change needed here.

- [ ] **Step 3: Commit engine fix**

```bash
cd vendor/miroshark && git add backend/app/services/simulation_runner.py && git commit -m "fix: use max_rounds as override, not ceiling

SaaS passes max_rounds to control round count per tier. The engine
was using min(config_rounds, max_rounds) which always picked the
config's 72 since max_rounds was 100. Now max_rounds directly sets
total_rounds when provided."
```

---

### Task 2: Retune tier parameters — rounds, model-len, agents

**Files:**
- Create: `alembic/versions/t1u2v3w4x5y6_retune_sim_params.py`
- Modify: `tests/conftest.py:105-122` (test fixtures)

New Alembic migration updates `model_routing` for all tiers:
- `max_rounds`: small=25, medium=100, large=200 (down from 100/150/200)
- `vllm_args`: add `--max-model-len 8192` (down from 32768) to 4× vLLM concurrency
- `target_agents`: small=10, medium=20, large=35 (slight reduction)

- [ ] **Step 1: Write test for new tier values**

In `tests/test_model_routing.py`, add:

```python
@pytest.mark.asyncio
async def test_small_tier_fits_timeout(client, auth_headers, seeded_routing):
    """Small tier max_rounds × estimated_round_time fits in timeout."""
    resp = await client.get("/api/jobs/tiers", headers=auth_headers)
    assert resp.status_code == 200
    tiers = resp.json()
    small = next(t for t in tiers if t["tier"] == "small")
    # At ~80s/round with 8K context, 25 rounds = 2000s < 2700s timeout
    assert small["max_rounds"] <= 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_routing.py::test_small_tier_fits_timeout -v`
Expected: FAIL (current max_rounds=100 > 30)

- [ ] **Step 3: Create Alembic migration**

Create `alembic/versions/t1u2v3w4x5y6_retune_sim_params.py`:

```python
"""retune simulation params for working tool calling

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-04-08
"""
from alembic import op

revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None

# With tool calling active, rounds take ~80s each (8K context, L40S).
# Budget: timeout / 80s, with 20% headroom for report generation.
TOOL_CALL_VLLM = "--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes"
OLD_VLLM = "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes"


def upgrade() -> None:
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 25, target_agents = 10,
            vllm_args = '--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'small';
    """)
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 100, target_agents = 20,
            vllm_args = '--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'medium';
    """)
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 200, target_agents = 35,
            vllm_args = '--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'large';
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 100, target_agents = 15,
            vllm_args = '--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'small';
    """)
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 150, target_agents = 25,
            vllm_args = '--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'medium';
    """)
    op.execute("""
        UPDATE model_routing
        SET max_rounds = 200, target_agents = 40,
            vllm_args = '--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes'
        WHERE sim_tier = 'large';
    """)
```

- [ ] **Step 4: Update test fixtures**

In `tests/conftest.py`, update the `seeded_routing` fixture (lines ~105-122) to use the new values:

```python
# small tier
ModelRouting(sim_tier="small", model_id="Qwen/Qwen3-14B", gpu_type="NVIDIA L40S",
             max_rounds=25, target_agents=10,
             vllm_args="--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes"),
# medium tier
ModelRouting(sim_tier="medium", model_id="Qwen/Qwen3-14B", gpu_type="NVIDIA L40S",
             max_rounds=100, target_agents=20,
             vllm_args="--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes"),
# large tier
ModelRouting(sim_tier="large", model_id="Qwen/Qwen3-14B", gpu_type="NVIDIA L40S",
             max_rounds=200, target_agents=35,
             vllm_args="--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes"),
```

Also update any test files that hardcode `--max-model-len 32768` in vllm_args assertions (check `tests/test_model_routing.py`, `tests/test_models.py`).

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/t1u2v3w4x5y6_retune_sim_params.py tests/
git commit -m "feat: retune sim params for working tool calling

Reduce max_rounds (25/100/200), lower max-model-len from 32K→8K
to 4× vLLM concurrency, and reduce target_agents slightly.
Rounds take ~80s with active tool calling; new params fit tier timeouts."
```

---

### Task 3: Update default VLLM_ARGS fallbacks

**Files:**
- Modify: `infra/docker/start.sh:17`
- Modify: `saas/jobs/config.py:61`

Update the hardcoded fallback defaults to use 8192 instead of 32768.

- [ ] **Step 1: Update start.sh**

Change line 17 from:
```bash
    ${VLLM_ARGS:---max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes} \
```
to:
```bash
    ${VLLM_ARGS:---max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes} \
```

- [ ] **Step 2: Update config.py**

Change the fallback in `saas/jobs/config.py:61` from:
```python
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes",
```
to:
```python
            "VLLM_ARGS": self.vllm_args or "--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes",
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker/start.sh saas/jobs/config.py
git commit -m "chore: update default VLLM_ARGS to 8K context"
```

---

### Task 4: Deploy and validate with prod sim

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Wait for CI/CD**

Watch `gh run list` for the deploy workflow to succeed.

- [ ] **Step 3: Run a small-tier test simulation**

Use agent-browser to launch a sim on simswarm.xyz and verify:
- Round count shows `/25` (not `/72` or `/100`)
- Rounds complete in ~60-90s each (not 5-6 min)
- Simulation completes within 45 min timeout
