# MiroShark → SimSwarm Complete Cutover — Implementation Plan

**Goal:** Eliminate every remaining dependency on `vendor/miroshark` and `vendor/mirofish`. Make `simswarm/` a fully self-contained engine that produces a populated `GraphSnapshot` and evolves agent beliefs between rounds.

**Non-goals:** Neo4j VPS decommission (deferred). Frontend changes (none needed — contract preserved).

---

## Phase A — Build `simswarm/graph.py`

**Why:** `engine.py:146` currently returns `GraphSnapshot(nodes=[], edges=[], metadata={})`. Frontend's Cytoscape viz gets empty data for every v2 sim.

**Files:**
- Create: `simswarm/graph.py` — `build_graph(entities, chat_log) → GraphSnapshot`
- Create: `tests/engine/test_graph.py`

**Node shape** (per agent): `{id, label, group, total_actions, total_posts, rounds_active}`

**Edge shape** (per interaction): `{source, target, type, weight}` where `type ∈ {follow, reply, mention, like}`

**Metadata:** `{total_nodes, total_edges, extracted_at_round}`

Edge sources from chat_log:
- `action_type == "follow"` → `action_args.target_id` as target
- `action_type == "reply"` → `action_args.post_id` / `action_args.target_agent` if present
- `action_type == "mention"` / `create_post` with `@name` → regex over text content
- Multiple interactions between the same pair collapse to one edge with `weight = count`

## Phase B — Activate belief dynamics in `engine.py`

**Why:** `simswarm/belief.py:update_beliefs()` exists but is never called. Agent `positions` / `confidence` stay at defaults → flat 0.0 sentiment observed in job 104/105.

**Approach:** After the per-round `asyncio.gather(...)` that executes agent actions, compute exposures for each agent from that round's posts (posts authored by *other* agents) and call `update_beliefs(state, posts, topic, own_likes, own_dislikes)`. Topic = the simulation's `goal` (single topic in v1 — sufficient for now; multi-topic is a follow-up).

**Stance inference:** lightweight — use the existing sentiment keyword lists in `simswarm/adapter.py` (`POSITIVE_WORDS` / `NEGATIVE_WORDS`) to score a post's stance in `[-1, 1]`. Extract into `simswarm/stance.py` so both places share the same words.

**Files:**
- Create: `simswarm/stance.py` — pure function `score_stance(text) → float`
- Modify: `simswarm/adapter.py` — import `POSITIVE_WORDS` / `NEGATIVE_WORDS` from the new module (no duplication)
- Modify: `simswarm/engine.py` — call `update_beliefs` per round; persist beliefs back onto `Agent.belief_state`
- Create: `tests/engine/test_belief_integration.py`

## Phase C — Wire graph construction into `engine.run()`

**Why:** Close the loop. Replace the stub at line 146 with the real builder.

**Files:**
- Modify: `simswarm/engine.py` — import `build_graph`, call before returning `SimulationResult`

No new tests beyond what Phase A added — graph construction is pure, already covered.

## Phase D — Delete `mirofish_adapter`

**Files:**
- Delete: `saas/adapters/mirofish_adapter.py`
- Delete: `tests/test_mirofish_adapter.py`, `tests/test_mirofish_adapter_branches.py`

Zero production callers — confirmed by audit.

## Phase E — Delete v1 pod code

**Files:**
- Delete: `infra/docker/run_job.py`, `graph_ops.py`, `results.py`, `simulation.py`, `results.py`
- Delete: `tests/test_entity_sentiment.py`, `tests/test_structured_results.py`, `tests/contracts/test_worker_contract.py`
- Modify: `infra/docker/worker_api.py` — remove any conditional v1/v2 branching (subprocess call should point solely at `run_job_v2.py`; already does after Task 17)
- Modify: `infra/docker/constants.py` — delete `MIROSHARK_BACKEND` constant and any now-unused imports
- Modify: `infra/docker/service_init.py` — keep `wait_for_neo4j` (still useful for Neo4j check) but drop any MiroShark Config imports

## Phase F — Delete vendor + strip Dockerfile

**Files:**
- `git rm` `vendor/miroshark/` (submodule removal — also edit `.gitmodules`)
- `git rm` `vendor/mirofish/` (same)
- Modify: `Dockerfile.worker`:
  - Delete lines 13-14 (COPY + pip install miroshark-requirements)
  - Delete line 52 (COPY vendor/miroshark/backend)
  - Delete the COPY line for `run_job.py` added in Phase E
  - Rebuild validation: worker image shrinks ~500MB

## Phase G — Deploy + verify

Push, watch CI/CD. Submit one small-tier sim with a seed naming real people. Confirm:
- `status=COMPLETED`
- Populated `result_graph` (nodes ≥ agent count, edges ≥ 0)
- Non-flat sentiment (at least one round with `positions[topic] != 0.0`)
- Worker image tag from `docker images` is new
- Old v1 code paths truly gone (grep prod logs for any `miroshark` / `MiroShark` / `run_job.py` references)
