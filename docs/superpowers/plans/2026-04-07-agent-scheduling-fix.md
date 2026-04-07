# Agent Scheduling Fix (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix agent starvation so all agents participate every round and `max_rounds` determines how many rounds run (not the LLM-generated time_config).

**Architecture:** Three changes: (1) modify `get_active_agents_for_round()` to activate all agents, (2) change 4 simulation loops to use `max_rounds` as the target, (3) remove the `_patch_sim_config` workaround. Plus an Alembic migration to scale rounds with tier.

**Tech Stack:** Python, Alembic, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-agent-scheduling-fix-design.md`

---

### Task 1: Activate All Agents Every Round

**Files:**
- Modify: `vendor/miroshark/backend/scripts/run_parallel_simulation.py:1100-1090` (simplify `get_active_agents_for_round`)

- [ ] **Step 1: Read the current function**

Read `vendor/miroshark/backend/scripts/run_parallel_simulation.py` lines 1100-1090 to see the current `get_active_agents_for_round()`.

- [ ] **Step 2: Replace the function**

Replace the entire `get_active_agents_for_round` function (lines 1100-1090) with:

```python
def get_active_agents_for_round(
    env,
    config: Dict[str, Any],
    current_hour: int,
    round_num: int
) -> List:
    """Return all agents as active for every round.

    The LLM has do_nothing as an available action — it decides whether to act,
    not a coin flip. This eliminates the activity_level, active_hours, and
    agents_per_hour starvation that caused sims to produce near-zero actions.
    """
    agent_configs = config.get("agent_configs", [])
    active_agents = []
    for cfg in agent_configs:
        agent_id = cfg.get("agent_id", 0)
        try:
            agent = env.agent_graph.get_agent(agent_id)
            active_agents.append((agent_id, agent))
        except Exception:
            pass
    return active_agents
```

- [ ] **Step 3: Commit**

```bash
git add vendor/miroshark/backend/scripts/run_parallel_simulation.py
git commit -m "fix: activate all agents every round, remove probabilistic selection"
```

---

### Task 2: Make `max_rounds` the Target in All Loops

**Files:**
- Modify: `vendor/miroshark/backend/scripts/run_parallel_simulation.py` (4 locations + 1 log section)

The same pattern appears in 4 simulation loops and 1 logging section. All need the same change.

- [ ] **Step 1: Fix Twitter loop (line ~1281-1291)**

Change from:
```python
    # Main simulation loop
    time_config = config.get("time_config", {})
    total_hours = time_config.get("total_simulation_hours", 72)
    minutes_per_round = time_config.get("minutes_per_round", 30)
    total_rounds = (total_hours * 60) // minutes_per_round
    
    # If max rounds specified, truncate
    if max_rounds is not None and max_rounds > 0:
        original_rounds = total_rounds
        total_rounds = min(total_rounds, max_rounds)
        if total_rounds < original_rounds:
            log_info(f"Rounds truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
```

To:
```python
    # Main simulation loop
    time_config = config.get("time_config", {})
    minutes_per_round = time_config.get("minutes_per_round", 30)

    # max_rounds is the target, not a ceiling — SaaS layer controls round count
    if max_rounds is not None and max_rounds > 0:
        total_rounds = max_rounds
    else:
        total_hours = time_config.get("total_simulation_hours", 72)
        total_rounds = (total_hours * 60) // minutes_per_round
```

- [ ] **Step 2: Fix Reddit loop (line ~1527-1538)**

Apply the exact same change as Step 1 to the Reddit loop section.

- [ ] **Step 3: Fix Polymarket loop (line ~1883-1893)**

Apply the exact same change as Step 1 to the Polymarket loop section.

- [ ] **Step 4: Fix synchronized parallel loop (line ~2182-2188)**

Change from:
```python
    time_config = config.get("time_config", {})
    total_hours = time_config.get("total_simulation_hours", 72)
    minutes_per_round = time_config.get("minutes_per_round", 30)
    total_rounds = (total_hours * 60) // minutes_per_round

    if max_rounds is not None and max_rounds > 0:
        total_rounds = min(total_rounds, max_rounds)
```

To:
```python
    time_config = config.get("time_config", {})
    minutes_per_round = time_config.get("minutes_per_round", 30)

    # max_rounds is the target, not a ceiling
    if max_rounds is not None and max_rounds > 0:
        total_rounds = max_rounds
    else:
        total_hours = time_config.get("total_simulation_hours", 72)
        total_rounds = (total_hours * 60) // minutes_per_round
```

- [ ] **Step 5: Update logging section (line ~2476-2488)**

Change from:
```python
    config_total_rounds = (total_hours * 60) // minutes_per_round
    
    log_manager.info(f"Simulation parameters:")
    log_manager.info(f"  - Total simulation duration: {total_hours} hours")
    log_manager.info(f"  - Time per round: {minutes_per_round} minutes")
    log_manager.info(f"  - Configured total rounds: {config_total_rounds}")
    if args.max_rounds:
        log_manager.info(f"  - Max rounds limit: {args.max_rounds}")
        if args.max_rounds < config_total_rounds:
            log_manager.info(f"  - Actual rounds to execute: {args.max_rounds} (truncated)")
```

To:
```python
    config_total_rounds = (total_hours * 60) // minutes_per_round
    actual_rounds = args.max_rounds if args.max_rounds and args.max_rounds > 0 else config_total_rounds

    log_manager.info(f"Simulation parameters:")
    log_manager.info(f"  - Total simulation duration: {total_hours} hours")
    log_manager.info(f"  - Time per round: {minutes_per_round} minutes")
    log_manager.info(f"  - Config rounds: {config_total_rounds}, max_rounds: {args.max_rounds}")
    log_manager.info(f"  - Actual rounds to execute: {actual_rounds}")
```

- [ ] **Step 6: Commit**

```bash
git add vendor/miroshark/backend/scripts/run_parallel_simulation.py
git commit -m "fix: use max_rounds as target round count, not ceiling"
```

---

### Task 3: Remove `_patch_sim_config` Workaround

**Files:**
- Modify: `infra/docker/run_job.py` (remove function + call)
- Remove: `tests/test_sim_config_patch.py` (tests for removed code)

- [ ] **Step 1: Remove `_patch_sim_config` function from run_job.py**

Delete the entire `_patch_sim_config` function (lines 59-110 in `infra/docker/run_job.py`) — from `def _patch_sim_config(` to the closing of the function.

- [ ] **Step 2: Remove the call in `run_pipeline()`**

In `run_pipeline()`, remove the line `_patch_sim_config(simulation_id, max_rounds)` (line ~135). The code should go directly from `prepare_simulation()` to `run_and_wait()`:

```python
        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)

        run_and_wait(simulation_id, max_rounds)
```

- [ ] **Step 3: Remove the test file**

Delete `tests/test_sim_config_patch.py` — the tests validated logic that no longer exists.

- [ ] **Step 4: Run existing tests to verify no breakage**

Run: `pytest tests/ -v --tb=short -x`
Expected: All PASS (the removed test file won't be collected)

- [ ] **Step 5: Commit**

```bash
git add infra/docker/run_job.py
git rm tests/test_sim_config_patch.py
git commit -m "refactor: remove _patch_sim_config workaround, fixed in engine directly"
```

---

### Task 4: Alembic Migration — Scale Rounds With Tier

**Files:**
- Create: `alembic/versions/q8r9s0t1u2v3_scale_rounds_with_tier.py`

- [ ] **Step 1: Create the migration file**

Create `alembic/versions/q8r9s0t1u2v3_scale_rounds_with_tier.py`:

```python
"""Scale max_rounds with tier: small=100, medium=150, large=200

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-04-07
"""
from alembic import op

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE model_routing SET max_rounds = 100 WHERE sim_tier = 'small';")
    op.execute("UPDATE model_routing SET max_rounds = 150 WHERE sim_tier = 'medium';")
    op.execute("UPDATE model_routing SET max_rounds = 200 WHERE sim_tier = 'large';")


def downgrade() -> None:
    op.execute("UPDATE model_routing SET max_rounds = 200 WHERE sim_tier IN ('small', 'medium', 'large');")
```

- [ ] **Step 2: Verify Alembic single head**

Run: `alembic heads`
Expected: Single head `q8r9s0t1u2v3`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/q8r9s0t1u2v3_scale_rounds_with_tier.py
git commit -m "feat: scale max_rounds with tier (small=100, medium=150, large=200)"
```

---

### Task 5: Final Verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS, no regressions

- [ ] **Step 2: Run ruff linter on changed files**

Run: `ruff check vendor/miroshark/backend/scripts/run_parallel_simulation.py infra/docker/run_job.py`
Expected: No errors

- [ ] **Step 3: Fix any lint issues and commit**

If ruff reports issues, fix and commit:
```bash
git add -u
git commit -m "fix: lint cleanup for agent scheduling fix"
```
