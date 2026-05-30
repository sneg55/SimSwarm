---
sidebar_label: Lineage & Differences
---

# How SimSwarm Differs from MiroFish and MiroShark

SimSwarm's intellectual lineage traces through two earlier projects — **MiroFish** and
**MiroShark** — but today's engine does not bundle or depend on either of them. SimSwarm is a
native, MIT-licensed rewrite that reimplements the ideas it found valuable in its own
architecture — including a clean-room reimplementation of the belief and prediction-market
modules, written from a behavioral specification rather than carried over from the AGPL source.
This page explains where it came from and what actually changed.

## The lineage

**MiroFish** is the original swarm-simulation engine (AGPL-3.0). It models agents posting and
reacting across two social platforms (Twitter + Reddit), stores its interaction graph in a
hosted graph service, and is built on the CAMEL-AI / OASIS agent framework with a Flask
server that spawns a subprocess per simulation backed by per-run SQLite. Agents are
effectively stateless between rounds. SimSwarm's earliest versions wrapped MiroFish directly
as an AGPL submodule under `vendor/`.

**MiroShark** ([github.com/aaronjmars/MiroShark](https://github.com/aaronjmars/MiroShark)) is
an AGPL-3.0 fork of MiroFish that added the features SimSwarm cared about most: a
**belief-state system** (per-agent stance, confidence, and trust), **sliding-window round
memory** with LLM summarization to survive long runs, a **prediction-market** platform with a
bridge coupling market prices and social sentiment, a self-hosted graph database, and
**task-level model routing** (a strong model for reasoning, a cheap one for bulk work).
SimSwarm migrated onto MiroShark's concepts during its second phase.

**SimSwarm** is the current native engine — a from-scratch rewrite (roughly 90% new code) that
keeps the *ideas* validated by MiroShark (prediction-market mechanics, belief-update dynamics,
effective prompts) while discarding the inherited framework and structure. Where earlier phases
had ported specific modules, those — the belief dynamics and the constant-product market maker —
were reimplemented clean-room from a behavioral specification, so the engine shares no source
with the AGPL upstream. SimSwarm no longer bundles or depends on MiroFish/MiroShark and is
published under the **MIT** license. (Conceptual credit is recorded in
[`NOTICE`](https://github.com/sneg55/SimSwarm/blob/main/NOTICE).)

## At a glance

| Dimension | MiroFish | MiroShark | SimSwarm |
|---|---|---|---|
| **License** | AGPL-3.0 | AGPL-3.0 | **MIT** |
| **Relationship** | Upstream origin | Fork of MiroFish | Native, clean-room rewrite — no shared source |
| **Runtime** | Flask server + subprocess-per-sim + per-run SQLite | Same (forked) | **Async Python library** — `await engine.run(config)` inside the GPU pod |
| **LLM loop** | CAMEL-AI / OASIS framework | CAMEL-AI / OASIS framework | **Direct vLLM `/v1/chat/completions` calls** — no framework layer |
| **Agent state** | Stateless between rounds | BeliefState (stance/confidence/trust) | BeliefState, reimplemented natively (see [Beliefs & Stance](../concepts/beliefs-and-stance.md)) |
| **Long-run memory** | Full context each round | Sliding-window LLM summarization | Bounded round memory in the core loop |
| **Environments** | Twitter + Reddit (hard-coded) | + prediction market + bridge | **Pluggable environments** — social, market, economic, custom (see [Environments](../concepts/environments.md)) |
| **Cross-environment** | Independent platforms | MarketMediaBridge | First-class [cross-environment bridge](../engine/architecture.md) |
| **Scenario sweeps** | — | — | **Built-in** `ScenarioSweep` over parameter combinations |
| **Model routing** | Single model | Task-level dual-tier | Tier/role routing (fast loop vs. smart offline) |

> The columns describe each project's design, not a benchmark. SimSwarm does not bundle or
> depend on MiroFish or MiroShark at runtime.

## What the rewrite changed

Three problems with the MiroShark-based engine (~37K lines across ~130 files) drove the
rewrite:

1. **Opaque LLM loop.** A heavy CAMEL-AI dependency meant debugging agent behavior required
   tracing framework internals. SimSwarm calls the model directly, so the entire
   request/response path is in code you can read.
2. **Inherited complexity.** Two separate hard-coded social platforms, dozens of SQL schema
   files, prompts scattered across many modules, and an embedding model for feed ranking —
   much of it inherited from upstream and not load-bearing. SimSwarm collapses this into a
   small set of focused modules and pluggable environments.
3. **Architecture limits.** Flask + subprocess + per-sim SQLite added IPC overhead, no shared
   state, and subprocess-spawning complexity. Because SimSwarm pods are ephemeral and run a
   single simulation, an in-process async library is simpler and fits the product direction
   (scenario sweeps, economic environments, structured policy inputs).

The result is documented in detail under [Engine Internals](../engine/architecture.md).

## Licensing: why MIT matters

MiroFish and MiroShark are both AGPL-3.0 — a strong copyleft license whose network-use clause
requires anyone offering the software as a service to make their complete corresponding source
available. SimSwarm reimplements these concepts in its own engine and no longer bundles the
AGPL upstream, and is published under the **MIT** license: you can self-host, modify, and build
on it — commercially or not — without copyleft obligations. See
[Open Source & Self-Hosting](./oss-and-self-host.md).

## Acknowledgements

SimSwarm owes its conceptual direction to MiroFish and to MiroShark by
[aaronjmars](https://github.com/aaronjmars/MiroShark). The belief dynamics, prediction-market
mechanics, and long-run memory strategy were proven there first and reimplemented independently
here; SimSwarm's contribution is a native, MIT-licensed engine that makes those ideas easier to
run, extend, and reason about. See [`NOTICE`](https://github.com/sneg55/SimSwarm/blob/main/NOTICE)
for attribution.
