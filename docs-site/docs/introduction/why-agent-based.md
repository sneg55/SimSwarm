---
sidebar_label: Why Agent-Based
---

# Why agent-based?

A single prompt to an LLM produces one voice's best guess. SimSwarm instead runs many
interacting agents over a series of rounds, and the answer to your goal *emerges* from
how those agents influence one another rather than from any one model call.

## What many interacting agents surface

- **Emergent belief and stance shifts.** Each agent carries an evolving belief state: a
  position on the topic (from opposed to supportive) and a confidence in that position.
  Every round, agents are exposed to the posts other agents authored, and their
  positions move based on who they trust, how much social engagement a post drew, and
  whether the idea is novel to them. A view that no single agent started with can spread,
  stall, or reverse across the population. See
  [Beliefs & Stance](../concepts/beliefs-and-stance.md).

- **Social and market environments.** Agents act through pluggable environments. In the
  social environment they post, reply, follow, and vote; in the market environment they
  buy and sell shares in prediction markets derived from your goal. The same population
  participates in both, so social narrative and market pricing move together. See
  [Environments](../concepts/environments.md).

- **Second-order effects.** A cross-environment bridge lets events from one environment
  (a market swing, a scheduled policy shock) reach agents in another. Effects can
  cascade: a market move feeds back into the conversation, which shifts beliefs, which
  changes subsequent trades. These chains are exactly what a single prompt cannot
  represent.

## Why a dedicated engine

SimSwarm runs on a native, async Python engine (`simswarm/`). The core loop is
deliberately transparent. Each round it gathers observations per agent, batches the
agent LLM calls under a concurrency limit, dispatches their actions to the right
environment, updates beliefs, ticks the environments, and snapshots round metrics. There
is no opaque agent framework between you and the behavior, which makes agent dynamics
inspectable and debuggable.

The result is a model of *interaction*, not just generation: you can watch coalitions
form, see where a narrative turned, and read the population-level outcome rather than a
single model's opinion.
