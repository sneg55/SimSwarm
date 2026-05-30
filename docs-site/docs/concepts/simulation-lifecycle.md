---
sidebar_label: Simulation Lifecycle
---

# Simulation Lifecycle

A simulation moves through a fixed sequence of phases, from the seed document you
provide to the four result views you read at the end.

## 1. Seed upload

You submit a seed document and a prediction goal. The seed is the source material the
scenario is built from; the goal is the plain-language question the run is meant to
answer.

## 2. Enrichment (optional)

Before the run, the seed can be enriched with live web and X/Twitter research via xAI
Grok. This produces a richer seed for the rest of the pipeline to work from. Enrichment
is best-effort — a failure here does not fail the job.

## 3. Setup: entities and markets

From the seed and goal, the platform derives the cast and the markets:

- **Entities** are extracted by an LLM call that lists the participants most relevant to
  the goal (see [Agents & Personas](./agents-and-personas.md)). Each entity becomes an
  agent in the run.
- **Prediction markets** are derived from the goal so the market environment has real
  markets to seed, rather than agents trading against an empty market.

## 4. Agent rounds

The engine runs the configured number of rounds. Each round it:

1. builds per-agent observations from every environment the agent is in (plus any
   scheduled events and scenario variables),
2. calls each agent's LLM with the tools its environments expose, gated by a concurrency
   limit,
3. dispatches each agent's chosen actions to the right environment and records them in
   the chat log,
4. updates every agent's beliefs from the posts authored that round (see
   [Beliefs & Stance](./beliefs-and-stance.md)),
5. ticks the environments and lets them publish cross-environment events through the
   bridge,
6. snapshots round metrics.

Larger tiers run more agents and longer horizons; the run is wrapped in a tier timeout.
The ephemeral GPU pod is torn down once on-pod post-processing (relation extraction, the
relation-merged graph, and persona enrichment) has finished and artifacts are uploaded.

## 5. Extraction

Once the rounds finish, deterministic extractors read the chat log and produce the
structured signals the result views need — stakeholder positions, coalitions, top
posts, market data, agent trajectories, and [story signals](./story-signals.md).

## 6. Graph and personas (on-pod)

Still on the GPU pod, right after `Engine.run` returns, the job runner assembles:

- the [entity graph](./entity-graph.md) — agents as nodes, with interaction edges from
  the chat log plus the LLM-derived semantic relationships, merged into the graph on the pod
  using the smart LLM (outside the engine's own loop);
- persona enrichment — the smart LLM expands each agent's activity summary into a persona.

Both run on the pod before it is torn down; on failure the pipeline keeps the
interaction-only graph and the one-line activity summaries.

## 7. Report (off-pod)

Only the [report](./reports.md) — a deep-analysis document the smart LLM writes by querying
the extracted signals through a tool-calling loop — runs off-pod, after the pod has uploaded
its artifacts and the GPU has been released. Any failure before the job reaches its completed
state marks the job failed.
