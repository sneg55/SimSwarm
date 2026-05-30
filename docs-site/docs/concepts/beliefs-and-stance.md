---
sidebar_label: Beliefs & Stance
---

# Beliefs & Stance

The dynamics that make SimSwarm more than a chat transcript live in how agents'
**beliefs** change over time. This page explains the idea conceptually; the precise
formulas are documented separately in the engine internals.

## Belief state

Each agent holds a belief state with three moving parts:

- **Position** — where the agent stands on the topic, on a scale from opposed to
  supportive.
- **Confidence** — how firmly that position is held.
- **Trust** — how much the agent weights each other agent's contributions.

An agent's position and confidence are rendered into plain-English bands in its prompt
(for example, "leaning supportive" with "moderate" confidence), so the simulated
participant behaves consistently with how its beliefs currently sit.

## Stance scoring

When an agent authors a post, the text is scored into a **stance** — a single number
from strongly negative to strongly positive — using sentiment analysis. This stance is
what other agents react to when they're exposed to the post. Scoring is deterministic
and runs without an LLM call.

## How beliefs update each round

After a round's posts are recorded, every agent updates its beliefs based on the posts
*other* agents authored (agents do not influence themselves). The update blends several
conceptual forces:

- **Pull toward stance** — exposure nudges an agent's position toward the stance of what
  it read, proportional to the gap between them.
- **Novelty** — an idea the agent hasn't seen before carries more weight than a repeat
  of something already in its exposure history.
- **Social proof** — posts with more engagement (likes) carry more influence, with a
  floor so that even zero-engagement posts still register.
- **Trust weighting** — content from agents the agent trusts more counts for more.
- **Resistance** — the more confident an agent already is, the smaller each nudge.
- **Trust evolution** — agents whose stance ends up aligned with the agent's resulting
  position gain trust; those who oppose it lose trust. Trust is learned over the run, not
  fixed.

Confidence itself shifts with the agent's own reception — likes on its posts build
confidence, dislikes erode it.

Because these forces compound across rounds, you get the population-level phenomena the
results surface: blocs forming around shared positions, a narrative gaining or losing
ground, and turning points where the balance shifts. The downstream
[story signals](./story-signals.md) and [report](./reports.md) read these outcomes back
out of the run.
