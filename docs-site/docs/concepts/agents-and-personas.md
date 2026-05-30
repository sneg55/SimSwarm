---
sidebar_label: Agents & Personas
---

# Agents & personas

An agent is one participant in the simulation. Every agent has an identity, a set of
environments it can act in, an evolving belief state, and a short memory of its recent
actions. During a run, an agent observes its environments each round and uses an LLM to
decide what to do: post, reply, follow, vote, trade, or do nothing.

## From seed to cast

Agents are generated from the seed document. An LLM call asks the smart model to list
the entities most relevant to the prediction goal and returns them as structured
records, each with a name, a type (for example a person or an organization), and a
short summary. Every extracted entity becomes one agent. The engine seeds the agent's
persona from the entity's name and summary so the agent acts as that participant from
its first round.

If the LLM extraction can't be parsed, the pipeline falls back to a simpler
capitalized-word scan of the seed so a run always has at least one agent.

## What an agent carries

- Persona: a short description of who the agent is, built from its source entity.
- Environments: the social and/or market environments it participates in.
- Belief state: its positions, confidence, and trust in other agents, which
  changes every round (see [Beliefs & Stance](./beliefs-and-stance.md)).
- Memory: a rolling window of its most recent actions, included in its context so
  behavior stays coherent across rounds without growing unbounded.

## Personas in the results

The seed-time persona is what drives behavior during the run. Separately, after the
simulation finishes, an LLM-backed step can rewrite each agent's profile into a longer
two-to-three-sentence persona based on what the agent actually did, drawing on its
sample posts and sentiment arc, replacing the default one-line activity summary shown in
the results. This is a descriptive, post-hoc enrichment. If it fails for an agent, the
one-line summary is used instead.
