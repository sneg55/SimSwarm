# Multi-Agent Expansion (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 15-40 agents per simulation (scaled by tier) instead of the current 1:1 entity-to-agent mapping, with multiple perspectives per entity and synthetic observer agents.

**Architecture:** Add `target_agents` column to `model_routing`, plumb it through SaaS → Celery → worker → engine. Modify the `SimulationConfigGenerator` to generate `target_agents` total agents in a single holistic LLM call instead of one-per-entity batches. The LLM decides how many sub-agents each entity gets and which observer types are relevant.

**Tech Stack:** Python, FastAPI, Celery, SQLAlchemy, Alembic, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-multi-agent-expansion-design.md`

**Depends on:** Phase 1 (agent scheduling fix) must be completed first.

---

### Task 1: Add `target_agents` to Database Model + Migration

**Files:**
- Modify: `saas/jobs/models.py:61-69` (add column to `ModelRouting`)
- Create: `alembic/versions/r9s0t1u2v3w4_add_target_agents.py`

- [ ] **Step 1: Add `target_agents` column to the `ModelRouting` model**

In `saas/jobs/models.py`, after the `vllm_args` line (line 69), add:

```python
    target_agents: Mapped[int] = mapped_column(Integer, default=5)
```

- [ ] **Step 2: Create the Alembic migration**

Create `alembic/versions/r9s0t1u2v3w4_add_target_agents.py`:

```python
"""Add target_agents to model_routing

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_routing", sa.Column("target_agents", sa.Integer(), server_default="5"))
    op.execute("UPDATE model_routing SET target_agents = 15 WHERE sim_tier = 'small';")
    op.execute("UPDATE model_routing SET target_agents = 25 WHERE sim_tier = 'medium';")
    op.execute("UPDATE model_routing SET target_agents = 40 WHERE sim_tier = 'large';")


def downgrade() -> None:
    op.drop_column("model_routing", "target_agents")
```

- [ ] **Step 3: Verify Alembic single head**

Run: `alembic heads`
Expected: Single head `r9s0t1u2v3w4`

- [ ] **Step 4: Commit**

```bash
git add saas/jobs/models.py alembic/versions/r9s0t1u2v3w4_add_target_agents.py
git commit -m "feat: add target_agents column to model_routing (small=15, medium=25, large=40)"
```

---

### Task 2: Plumb `target_agents` Through SaaS → Celery → Worker

**Files:**
- Modify: `saas/jobs/api.py:97-113` (pass target_agents to Celery task)
- Modify: `saas/jobs/tasks.py:41-57` (accept target_agents param)
- Modify: `saas/jobs/config.py:23-40` (add to JobConfig)
- Modify: `saas/jobs/pipeline.py:88-97` (include in /job POST)
- Modify: `infra/docker/worker_api.py:57,152-177` (accept and forward)
- Modify: `infra/docker/run_job.py` (accept and forward to prepare_simulation)
- Modify: `infra/docker/simulation.py` (accept and forward to SimulationManager)

- [ ] **Step 1: Add `target_agents` to `JobConfig`**

In `saas/jobs/config.py`, add after line 39 (`forecast_days`):

```python
    target_agents: int = 5
```

- [ ] **Step 2: Add `target_agents` to the Celery task signature**

In `saas/jobs/tasks.py`, add `target_agents: int = 5,` parameter after `forecast_days` (line 56) in `run_simulation_task`:

```python
    forecast_days: int | None = None,
    target_agents: int = 5,
    upload_urls: dict | None = None,
```

And in the `JobConfig(...)` constructor (line ~81-99), add:

```python
        target_agents=target_agents,
```

- [ ] **Step 3: Pass `target_agents` from API to Celery**

In `saas/jobs/api.py`, add to the `run_simulation_task.delay(...)` call (after line 111, `forecast_days`):

```python
            target_agents=routing.target_agents,
```

- [ ] **Step 4: Include `target_agents` in the /job POST to worker**

In `saas/jobs/pipeline.py`, add to the `submit_job` POST body (line 91-97):

```python
        "target_agents": config.target_agents,
```

- [ ] **Step 5: Accept `target_agents` in worker API**

In `infra/docker/worker_api.py`, in `submit_job()` (line 158), add:

```python
    target_agents = data.get("target_agents", 5)
```

Pass it to `_run_pipeline`:

```python
    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds, forecast_days, upload_urls, target_agents),
        daemon=True,
    )
```

Update `_run_pipeline` signature (line 57) to accept `target_agents`:

```python
def _run_pipeline(seed_text, goal, max_rounds, forecast_days=None, upload_urls=None, target_agents=5):
```

And add the CLI arg to `run_job.py` invocation (line 67-74):

```python
                    "--target-agents", str(target_agents),
```

- [ ] **Step 6: Accept `target_agents` in `run_job.py`**

In `infra/docker/run_job.py`, add to the argparse section (after `--output-dir`):

```python
    parser.add_argument("--target-agents", type=int, default=5)
```

Pass it to `run_pipeline`:

```python
    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir, args.target_agents)
```

Update `run_pipeline` signature:

```python
def run_pipeline(seed_text: str, goal: str, max_rounds: int, output_dir: str, target_agents: int = 5) -> dict:
```

- [ ] **Step 7: Forward `target_agents` to `prepare_simulation`**

In `infra/docker/simulation.py`, update `prepare_simulation` to accept and forward:

```python
def prepare_simulation(project_id: str, graph_id: str, seed_text: str, goal: str, storage, target_agents: int = 5) -> str:
```

Pass to `sm.prepare_simulation(...)`:

```python
    sm.prepare_simulation(
        simulation_id=simulation_id,
        simulation_requirement=goal,
        document_text=seed_text,
        use_llm_for_profiles=True,
        progress_callback=_progress,
        storage=storage,
        target_agents=target_agents,
    )
```

And update the call in `run_pipeline`:

```python
        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage, target_agents)
```

- [ ] **Step 8: Commit**

```bash
git add saas/jobs/config.py saas/jobs/tasks.py saas/jobs/api.py saas/jobs/pipeline.py \
       infra/docker/worker_api.py infra/docker/run_job.py infra/docker/simulation.py
git commit -m "feat: plumb target_agents from model_routing through to engine"
```

---

### Task 3: Accept `target_agents` in MiroShark Engine

**Files:**
- Modify: `vendor/miroshark/backend/app/services/simulation_manager.py:235-431` (accept and forward)
- Modify: `vendor/miroshark/backend/app/services/simulation_config_generator.py:259-378` (accept param)

- [ ] **Step 1: Add `target_agents` to `SimulationManager.prepare_simulation()`**

In `vendor/miroshark/backend/app/services/simulation_manager.py`, add `target_agents: int = 5` parameter to `prepare_simulation()` (after `storage` param, line 244):

```python
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3,
        storage: 'GraphStorage' = None,
        target_agents: int = 5,
    ) -> SimulationState:
```

Pass it to `config_generator.generate_config()` (line ~422-431):

```python
            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit,
                target_agents=target_agents,
            )
```

- [ ] **Step 2: Add `target_agents` to `SimulationConfigGenerator.generate_config()`**

In `vendor/miroshark/backend/app/services/simulation_config_generator.py`, add `target_agents: int = 5` to `generate_config()` signature (line ~259-270):

```python
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        target_agents: int = 5,
    ) -> SimulationParameters:
```

Store it for use in the agent generation step. Pass it to `_generate_agent_configs_batch` (will be modified in Task 4).

In the agent generation section (~lines 307-325), change from batching per-entity to a single call:

```python
        # ========== Step 3: Generate Agent configs (multi-perspective) ==========
        report_progress(3, f"Generating {target_agents} agent configurations...")
        all_agent_configs = self._generate_agent_configs_multi(
            context=context,
            entities=entities,
            simulation_requirement=simulation_requirement,
            target_agents=target_agents,
        )
        reasoning_parts.append(f"Agent configs: successfully generated {len(all_agent_configs)}")
```

- [ ] **Step 3: Commit**

```bash
git add vendor/miroshark/backend/app/services/simulation_manager.py \
       vendor/miroshark/backend/app/services/simulation_config_generator.py
git commit -m "feat: accept target_agents in MiroShark config generation pipeline"
```

---

### Task 4: Implement Multi-Perspective Agent Generation

**Files:**
- Modify: `vendor/miroshark/backend/app/services/simulation_config_generator.py` (new method `_generate_agent_configs_multi`)

- [ ] **Step 1: Add the new `_generate_agent_configs_multi` method**

Add this method to `SimulationConfigGenerator` (after `_generate_agent_configs_batch`, around line 1050):

```python
    def _generate_agent_configs_multi(
        self,
        context: str,
        entities: List[EntityNode],
        simulation_requirement: str,
        target_agents: int = 15,
    ) -> List[AgentActivityConfig]:
        """Generate multiple agents per entity + synthetic observers.

        Instead of 1:1 entity-to-agent, the LLM decides how to allocate
        target_agents across the entities and adds observer agents.
        """
        # Build entity summary for the prompt
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for e in entities:
            entity_list.append({
                "name": e.name,
                "type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else "",
            })

        prompt = f"""Based on the following simulation scenario, generate {target_agents} diverse agent profiles.

Simulation requirement: {simulation_requirement}

## Entities from knowledge graph
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Rules
1. Important entities should have MULTIPLE representatives with different perspectives.
   Example: "Apple" → a CEO (strategic), an engineer (technical), a PR lead (public messaging).
2. Not all agents should be direct stakeholders. Include OUTSIDE OBSERVERS who watch, analyze,
   and react without being directly involved — journalists, industry analysts, commentators,
   affected bystanders relevant to this specific topic.
3. Each agent must have a UNIQUE name (real or realistic), a clear role, and a distinct viewpoint.
4. Generate exactly {target_agents} agents total.
5. Every agent must be linked to a source entity OR marked as an observer.

## Return JSON (no markdown):
{{
    "agents": [
        {{
            "agent_id": 0,
            "entity_name": "<source entity name or 'Observer'>",
            "name": "<unique agent name>",
            "role": "<specific role/title>",
            "activity_level": <0.1-0.9>,
            "posts_per_hour": <float>,
            "comments_per_hour": <float>,
            "response_delay_min": <int minutes>,
            "response_delay_max": <int minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <0.5-3.0>
        }},
        ...
    ]
}}"""

        system_prompt = (
            "You are a social media simulation designer. Return pure JSON.\n\n"
            "AGENT DESIGN PRINCIPLES:\n"
            "- Stakeholder agents represent specific people or roles within an entity.\n"
            "- Observer agents are independent voices: journalists cover the story, "
            "analysts evaluate impact, consumers react, regulators watch.\n"
            "- Diversity of stance is critical — not everyone agrees. Include supporters, "
            "opponents, and skeptics.\n"
            "- influence_weight: 2.0-3.0 for executives/institutions, 1.0-2.0 for "
            "experts/journalists, 0.5-1.0 for regular people.\n"
            "- stance must reflect realistic positions, not random assignment."
        )

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            agents_data = result.get("agents", [])
        except Exception as e:
            logger.warning(f"Multi-agent generation failed: {e}, falling back to 1:1")
            return self._generate_agent_configs_batch(
                context=context,
                entities=entities,
                start_idx=0,
                simulation_requirement=simulation_requirement,
            )

        # Build AgentActivityConfig objects
        configs = []
        for i, agent in enumerate(agents_data[:target_agents]):
            agent_id = i
            # Find source entity UUID if linked
            entity_uuid = ""
            entity_type = "Observer"
            source_name = agent.get("entity_name", "Observer")
            for e in entities:
                if e.name.lower() == source_name.lower():
                    entity_uuid = e.uuid
                    entity_type = e.get_entity_type() or "Unknown"
                    break

            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity_uuid,
                entity_name=agent.get("name", f"Agent_{agent_id}"),
                entity_type=entity_type,
                activity_level=agent.get("activity_level", 0.5),
                posts_per_hour=agent.get("posts_per_hour", 1.0),
                comments_per_hour=agent.get("comments_per_hour", 1.0),
                active_hours=list(range(0, 24)),  # All hours — scheduling handled by engine
                response_delay_min=agent.get("response_delay_min", 5),
                response_delay_max=agent.get("response_delay_max", 60),
                sentiment_bias=agent.get("sentiment_bias", 0.0),
                stance=agent.get("stance", "neutral"),
                influence_weight=agent.get("influence_weight", 1.0),
            )
            configs.append(config)

        logger.info(f"Multi-agent generation: {len(configs)} agents from {len(entities)} entities")
        return configs
```

- [ ] **Step 2: Verify the old `_generate_agent_configs_batch` is still callable as fallback**

Read `_generate_agent_configs_batch` to confirm it still exists and accepts the same params. It's used as the fallback in the `except` block above.

- [ ] **Step 3: Commit**

```bash
git add vendor/miroshark/backend/app/services/simulation_config_generator.py
git commit -m "feat: multi-perspective agent generation with observers"
```

---

### Task 5: Update Profile Generation for Expanded Agent Count

**Files:**
- Modify: `vendor/miroshark/backend/app/services/simulation_manager.py` (profile generation must handle more agents than entities)

The current profile generation in `prepare_simulation()` generates one profile per entity (Phase 2 in the prepare flow, lines ~312-401). With multi-agent expansion, we need profiles for `target_agents` count, not `len(entities)`.

- [ ] **Step 1: Generate profiles after config generation**

The current flow is: entities → profiles → config. But with multi-agent expansion, config determines the agent roster. Reorder to: entities → config (with target_agents) → profiles.

In `prepare_simulation()`, move the profile generation (Phase 2) to AFTER config generation (Phase 3). The profiles should be generated from the agent configs, not from raw entities.

After config generation produces `sim_params` with `all_agent_configs`, generate profiles from those configs:

```python
            # ========== Phase 3 (moved up): Generate simulation config ==========
            # ... (existing config generation code, now with target_agents) ...

            # ========== Phase 2 (moved after config): Generate profiles from agent configs ==========
            # Create synthetic entity-like objects for each agent config
            profile_entities = []
            for ac in sim_params.agent_configs:
                # Find the original entity if it exists
                original = next((e for e in filtered.entities if e.uuid == ac.entity_uuid), None)
                if original:
                    profile_entities.append(original)
                else:
                    # Create a minimal entity for synthetic/observer agents
                    from app.services.entity_reader import EntityNode
                    synthetic = EntityNode(
                        uuid=f"synthetic_{ac.agent_id}",
                        name=ac.entity_name,
                        summary=f"{ac.entity_name} - {ac.entity_type} ({ac.stance})",
                        labels=[ac.entity_type],
                        attributes={},
                        edges=[],
                    )
                    profile_entities.append(synthetic)

            profiles = generator.generate_profiles_from_entities(
                entities=profile_entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,
                parallel_count=parallel_profile_count,
                realtime_output_path=realtime_output_path,
                output_platform=realtime_platform,
            )
```

- [ ] **Step 2: Commit**

```bash
git add vendor/miroshark/backend/app/services/simulation_manager.py
git commit -m "feat: generate profiles from expanded agent configs, not raw entities"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Run ruff linter on changed files**

Run: `ruff check saas/jobs/models.py saas/jobs/api.py saas/jobs/tasks.py saas/jobs/config.py saas/jobs/pipeline.py infra/docker/worker_api.py infra/docker/run_job.py infra/docker/simulation.py`
Expected: No errors

- [ ] **Step 3: Fix any lint issues and commit**

```bash
git add -u
git commit -m "fix: lint cleanup for multi-agent expansion"
```
