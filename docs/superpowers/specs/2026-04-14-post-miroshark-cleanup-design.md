# Post-MiroShark Cutover Cleanup

**Date:** 2026-04-14
**Status:** Design approved, ready for implementation plan

## Context

After the MiroShark → native-engine cutover, triage surfaced a list of remaining quality and operational gaps. This spec addresses the five worth fixing now and references GH issues for the two that are being deferred.

- **SimSwarm#70** — empty social graph for analytical topics (deferred, engine-level work)
- **SimSwarm#71** — Job 107 zeroed result_structured/enrichment_citations (deferred, one-off historical)

## Goals

1. Restore per-node sentiment in the graph so nodes render with color rather than neutral gray.
2. Replace one-line activity-summary personas with LLM-generated 2–3 sentence personas.
3. Tally dislikes in top-posts extraction (currently always 0).
4. Tighten the wizard's enrich-web checkbox so broad label clicks can't silently toggle it.
5. Remove the duplicated worker-image build across `deploy.yml` and `build-worker.yml`.

## Non-Goals

- No changes to the MiroShark code path (fully cut over).
- No seeding/inferring social edges for analytical topics (#70).
- No repair utility for the single job 107 (#71).
- No visual redesign of the wizard beyond the label-scope adjustment.

## Design

Two-PR delivery to keep blast radius contained:

- **PR 1 — Simulation output quality:** (1) sentiment, (2) personas, (3) dislikes. All touch the extractor/adapter layer.
- **PR 2 — Frontend + CI safety:** (4) checkbox label, (5) deploy dedup. Unrelated to the sim pipeline.

### 1. Per-node sentiment in the graph adapter

**Current state**
`saas/jobs/graph_adapter.py:57` sets `"sentiment": n.get("sentiment", 0.0)`. The native engine doesn't surface per-entity sentiment on the node dict, so this is always 0.0 and every node renders neutral.

**Data already available**
`simswarm/extractor_activity.py:51` (`extract_agent_trajectories`) already computes per-round-per-agent sentiment via `score_sentiment(combined_text)`.

**Change**
1. At the graph-adapter call site (where `_adapt_node` is invoked for each node), build a `sentiment_by_agent: dict[str, float]` by averaging each agent's round-level sentiments from the trajectory list.
2. Pass that map into `_adapt_node` alongside `conn_count`.
3. `_adapt_node` reads `sentiment_by_agent.get(node_key, 0.0)` where `node_key` matches by agent id first, then name as fallback.

No engine changes. Estimated ~30 LOC.

### 2. LLM-backed personas

**Current state**
`simswarm/extractor_activity.py:135` (`_profile_summary`) returns strings like `"12 posts, 15 actions across 8 rounds on twitter."` as the persona. That's what the Agents tab and profile cards display.

**Change**
New module `simswarm/personas.py` that mirrors the architecture of `simswarm/relations.py` (commit 558f322):

- Function: `extract_personas(agents: list[AgentData], posts_by_agent: dict, trajectories: list) -> dict[str, str]`
- Build compact input per agent: name, platform(s), activity counts, 3–5 sampled posts (spread across rounds), sentiment arc summary (e.g., "starts positive, turns negative by round 5").
- Batched single LLM call with JSON-mode response returning `{agent_id: persona_text}` for all agents at once.
- Reuse the same LLM client the relations extractor uses.
- On any LLM failure (timeout, parse error, partial response), fall back to the current one-liner **per-agent** so a job never fails because of personas.
- Replace `_profile_summary` output in `extract_profiles` with the LLM persona when available, else the existing one-liner.

Shipping on by default (no env flag gate) per triage decision.

**Prompt shape**
System: "You write concise 2–3 sentence agent personas from simulation activity. Capture stance, tone, and topical focus. No meta-commentary."
User: JSON payload of all agents' sampled data.
Output: JSON object mapping `agent_id → persona_text`.

### 3. Dislikes tally

**Current state**
`simswarm/extractor_posts.py:68` hardcodes `"num_dislikes": 0`. The native social environment (`simswarm/environments/social.py:154`) does track `post.dislikes` on vote actions.

**Change**
In `extract_top_posts`, read `post.dislikes` from the same post object that currently feeds `num_likes`. Mirror the likes code path exactly.

### 4. Enrich-web checkbox label scope

**Current state**
`frontend/src/views/NewSimulation.vue:16-23` wraps both the checkbox input and the multi-line description `<p>` in a single `<label cursor-pointer>`. Broad text clicks (from agent-browser or accidental user clicks on the description) toggle the checkbox.

**Change**
- Keep `<label>` around the `<input>` and the short title span ("Enrich with web research") — preserves a11y.
- Move the descriptive `<p>` out of the label, but keep it in the parent flex container so visual grouping is preserved.
- Result: clickable-to-toggle area shrinks from the whole block to just the input and title.

### 5. Deploy worker-image build dedup

**Current state**
- `.github/workflows/deploy.yml:41-54` embeds a full worker-image build-and-push.
- `.github/workflows/build-worker.yml:56-66` runs on the same triggers and pushes the same tags (`ghcr.io/.../worker:<sha>` and `:latest`).
Two concurrent builds race on every push to `main`.

**Change (Option A)**
- Delete the embedded build step in `deploy.yml`.
- Change `deploy.yml`'s trigger from `push: main` to `workflow_run: { workflows: [Build Worker Image], types: [completed], branches: [main] }`.
- Add a top-level `if: github.event.workflow_run.conclusion == 'success'` guard so deploy skips when the build fails.
- Deploy then references the image tag `ghcr.io/.../worker:<sha>` where `<sha>` comes from `github.event.workflow_run.head_sha`.

**Known caveat**
`workflow_run` triggers always run against the default branch's workflow definition, so changes to `deploy.yml` in a feature branch won't take effect until merged. This is acceptable for a deploy workflow that only runs on `main`.

## Testing

### PR 1 (sim output quality)

- **Sentiment:** unit test that passes a synthetic trajectory list into the graph adapter and asserts nodes receive the averaged sentiment, with 0.0 fallback for unknown nodes.
- **Personas:** unit test with mocked LLM client asserting (a) batched call shape, (b) happy-path mapping to `extract_profiles` output, (c) fallback to one-liner on LLM error, on parse error, and on missing agent in response.
- **Dislikes:** extend the existing `extract_top_posts` test with a synthetic post that has non-zero `dislikes` and assert it surfaces.
- Manual spot-check: run a small sim end-to-end, confirm Agents tab shows richer personas and graph has colored nodes.

### PR 2 (frontend + CI)

- **Checkbox:** Vitest component test that simulates a click on the description `<p>` and asserts `enrichWeb` is unchanged; click on the title span still toggles it.
- **Deploy dedup:** dry-run via a throwaway branch PR to `main` with the YAML change; verify only one build job appears in Actions and that deploy chains off its success. Revert if misbehaving.

## Rollout

- PR 1 ships first. If personas cause any user-visible regression, revert just the `extract_profiles` call site to fall back to `_profile_summary` — sentiment and dislikes are independent and can stay.
- PR 2 ships after PR 1 is green in prod for at least one real job.

## Out of Scope (tracked elsewhere)

- Empty social graph for analytical topics — SimSwarm#70
- Job 107 repair — SimSwarm#71
