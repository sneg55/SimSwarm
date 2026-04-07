# Multi-Agent Expansion (Phase 2)

**Date:** 2026-04-07
**Phase:** 2 of 2 (Phase 1: agent scheduling fix)
**Depends on:** Phase 1 must be deployed first (all agents active every round, `max_rounds` as target)
**Trigger:** Sim 62 + 63 produced only 4 agents from 5 graph entities due to 1:1 entity-to-agent mapping. No mechanism to generate multiple perspectives per entity or synthetic observer agents.

## Problem Analysis

The current pipeline creates exactly one agent per graph entity. With a typical seed text producing 5-8 entities, simulations have 4-8 agents — too few for meaningful social dynamics (coalition formation, echo chambers, opinion shifts).

The `SimulationConfigGenerator` receives filtered entities and generates one `AgentActivityConfig` per entity via an LLM call. There is no mechanism to:
- Create multiple sub-agents per entity (CEO perspective vs engineer vs PR)
- Generate synthetic observer agents (journalists, analysts, affected bystanders)
- Target a specific agent count based on tier

## Design

Modify the MiroShark engine directly (`vendor/miroshark/`) to generate multi-perspective agents per entity plus observer agents, targeting a configurable count per tier.

### Section 1: Modify `SimulationConfigGenerator` Prompt

**Where:** `vendor/miroshark/backend/app/services/simulation_config_generator.py`, `_generate_agent_configs_batch()`

**Current:** Prompt asks the LLM to generate one agent config per entity. Receives a batch of entities, returns one `AgentActivityConfig` each.

**New:** Prompt receives all entities + `target_agents` count. Instructs the LLM to:
- Generate `target_agents` total agent profiles
- Important entities get multiple representatives with different perspectives (e.g. CEO, engineer, PR spokesperson)
- Include outside observers who watch, analyze, and react without being directly involved (journalists, analysts, commentators, affected bystanders)
- Each agent needs a unique name, role, stance, and personality

Prompt guidance (added to the existing prompt structure):
> "Generate {target_agents} agent profiles from these entities. Important entities should have multiple representatives with different perspectives (e.g. a CEO, an engineer, a PR spokesperson). Not all agents should be direct stakeholders — include outside observers who watch, analyze, and react without being directly involved (journalists, analysts, commentators, affected bystanders). Each agent needs a unique name, role, stance, and personality."

The LLM decides how many sub-agents each entity gets and which observer types are relevant to the topic — no hardcoded categories or allocation formulas.

### Section 2: Pass `target_agents` Through the Pipeline

**Where:** Database → SaaS API → Celery → Worker → Engine

Flow:
1. **`model_routing` table** — new column `target_agents INT` (small=15, medium=25, large=40). Default=5 to preserve existing sims.
2. **`saas/jobs/api.py`** — reads `target_agents` from routing row (same pattern as `max_rounds`)
3. **`saas/jobs/config.py`** — add `target_agents` field to `JobConfig`
4. **`saas/jobs/tasks.py`** — passes `target_agents` as Celery task arg
5. **`infra/docker/worker_api.py`** — accepts `target_agents` in `/job` payload
6. **`infra/docker/run_job.py`** — passes to `prepare_simulation()`
7. **`infra/docker/simulation.py`** — passes to `SimulationManager.prepare_simulation()`
8. **`vendor/miroshark/` SimulationManager** → `SimulationConfigGenerator.generate_config()` — receives and uses `target_agents`

Alembic migration adds the column with default=5.

### Section 3: Restructure Batch Generation for Target Count

**Where:** `vendor/miroshark/backend/app/services/simulation_config_generator.py`, `generate_config()`

**Current:** Entities split into batches of `AGENTS_PER_BATCH=15`, each batch gets a separate LLM call producing 1 agent per entity.

**New:** Single holistic LLM call with all entities + `target_agents`. The LLM needs the full entity list to allocate agents proportionally — batching per-entity defeats this.

- If `target_agents <= 20`: single LLM call returns all agent configs.
- If `target_agents > 20`: two calls — first generates the roster (names, roles, stances for all agents), second fills in personality details in batches of 15-20. Keeps prompt size manageable.

Output is still `List[AgentActivityConfig]` — downstream code doesn't change.

## Files Changed

| File | Change |
|---|---|
| `vendor/miroshark/backend/app/services/simulation_config_generator.py` | New prompt, single-call generation, accept `target_agents` param |
| `vendor/miroshark/backend/app/services/simulation_manager.py` | Pass `target_agents` to config generator |
| `infra/docker/simulation.py` | Accept + forward `target_agents` |
| `infra/docker/run_job.py` | Accept + forward `target_agents` |
| `infra/docker/worker_api.py` | Accept `target_agents` in `/job` payload |
| `saas/jobs/tasks.py` | Pass `target_agents` as Celery task arg |
| `saas/jobs/api.py` | Read `target_agents` from model_routing |
| `saas/jobs/config.py` | Add `target_agents` to `JobConfig` |
| New Alembic migration | Add `target_agents` column to `model_routing` |

## Not Changed

- Agent scheduling — handled in Phase 1 (all agents active every round)
- Round counts — handled in Phase 1 (`model_routing.max_rounds`)
- Graph construction — entity extraction stays the same; more agents doesn't mean more graph nodes
- Frontend — agent count is already read from the confidence metrics array; more agents appear automatically
