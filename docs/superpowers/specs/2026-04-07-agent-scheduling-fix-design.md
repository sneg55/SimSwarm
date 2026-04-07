# Agent Scheduling Fix (Phase 1)

**Date:** 2026-04-07
**Phase:** 1 of 2 (Phase 2: multi-agent expansion per entity)
**Trigger:** Sim 62 + 63 — 200 configured rounds but only 9 actions produced. Root cause: probabilistic agent selection + time-of-day filtering + `max_rounds` used as ceiling not target.

## Problem Analysis

Three compounding issues in the MiroShark simulation runner cause agent starvation:

1. **`max_rounds` is a ceiling, not a target.** Actual round count comes from `time_config.total_simulation_hours / minutes_per_round`. If the LLM-generated time_config produces fewer rounds, `min(config_rounds, max_rounds)` caps downward. Sim 62 got 10 rounds instead of 200.

2. **Probabilistic agent selection starves small agent pools.** `get_active_agents_for_round()` uses `activity_level=0.5` (coin flip per agent), `agents_per_hour_min/max` (corrected to 1-2 for 4 agents), and `active_hours` (8am-10pm default). Result: most rounds have 0 active agents. With 4 agents, expected active count per work-hour round is ~0-1.

3. **Time-of-day filtering eliminates agents for 9+ hours/day.** Agents default to `active_hours=[8..22]`. Simulation starts at hour 0 (midnight). Rounds 0-7 have zero eligible agents regardless of other settings.

The `_patch_sim_config` workaround in `infra/docker/run_job.py` addressed symptoms (patching `total_simulation_hours` and `off_peak_activity_multiplier`) but didn't fix the root cause. Sim 63 confirmed: patches fired correctly but still only 9 actions produced.

## Design

Fix the engine directly in `vendor/miroshark/` (private fork). Remove the workaround from `run_job.py`.

### Section 1: Make `max_rounds` the target

**Where:** `vendor/miroshark/backend/scripts/run_parallel_simulation.py`
- Twitter loop (lines ~1214-1224)
- Reddit loop (lines ~1413-1416)

**Current:**
```python
total_rounds = (total_hours * 60) // minutes_per_round
if max_rounds is not None and max_rounds > 0:
    total_rounds = min(total_rounds, max_rounds)
```

**New:**
```python
if max_rounds is not None and max_rounds > 0:
    total_rounds = max_rounds
else:
    total_rounds = (total_hours * 60) // minutes_per_round
```

The SaaS layer owns round counts via `model_routing.max_rounds`. The engine respects it as a target. The time_config still provides `minutes_per_round` for simulated-hour calculation (used in logging), but doesn't determine how many rounds run.

### Section 2: Activate all agents every round

**Where:** `vendor/miroshark/backend/scripts/run_parallel_simulation.py`, `get_active_agents_for_round()` (lines ~1040-1090)

**Current:** Probabilistic selection with `activity_level`, `active_hours`, `agents_per_hour_min/max`, and time-of-day multipliers.

**New:** Activate all agents unconditionally:
```python
def get_active_agents_for_round(env, config, current_hour, round_num):
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

The LLM already has `do_nothing` as an available action — it decides whether to act, not a coin flip. This eliminates the `active_hours`, `activity_level`, and `agents_per_hour` starvation paths entirely.

### Section 3: Remove `_patch_sim_config` workaround

**Where:** `infra/docker/run_job.py`

Remove the `_patch_sim_config()` function and its call in `run_pipeline()`. No longer needed since sections 1 and 2 fix the engine directly.

Keep `MIN_GRAPH_ENTITIES = 5` guard — still valid.

### Section 4: Update `model_routing` round counts

**Where:** Alembic migration updating `model_routing` table

With all agents active every round, fewer rounds are needed for the same total interactions. New values:

| Tier | Current `max_rounds` | New `max_rounds` |
|------|---------------------|-----------------|
| small | 200 | 100 |
| medium | 200 | 150 |
| large | 200 | 200 |

### Section 5: Apply to Reddit loop

The parallel runner has two near-identical loops (Twitter lines ~1214-1290, Reddit lines ~1413-1479). Both need the Section 1 change (`total_rounds = max_rounds`). Both already share `get_active_agents_for_round()` so Section 2 applies to both automatically.

Check if Polymarket has a separate loop needing the same fix.

## Files Changed

| File | Change |
|---|---|
| `vendor/miroshark/backend/scripts/run_parallel_simulation.py` | `max_rounds` as target + activate all agents + Reddit loop |
| `infra/docker/run_job.py` | Remove `_patch_sim_config` function and call |
| New Alembic migration | Update `model_routing` round counts |

## Not Changed

- `vendor/miroshark/` agent config generator — Phase 2 scope
- `saas/jobs/alerts.py` — enrichment alerting stays (from earlier guardrails work)
- `infra/docker/results.py` — metrics fixes stay (Rounds + Trades)
- `MIN_GRAPH_ENTITIES` guard — stays in `run_job.py`
