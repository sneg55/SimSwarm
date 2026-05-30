---
sidebar_label: Reports
---

# Reports

The **report** is the deep-analysis document a simulation produces — the result view
most readers start with. It's written by the smart LLM, but it is grounded in the
simulation's extracted signals so that every claim traces back to something that
actually happened in the run.

## How a report is assembled

Report generation is a multi-turn, tool-calling loop rather than a single prompt:

1. The generator starts the LLM with a system prompt that states the goal and lays out
   the exact sections and format the report must follow.
2. On each turn the LLM can call query tools over the finished simulation instead of
   guessing. The available tools let it pull the first *N* posts (in chat-log order, not
   engagement-ranked), detect coalitions among agents, fetch a summary for a specific agent,
   and read an agent's trajectory across rounds.
3. When the LLM stops calling tools and returns prose, that markdown becomes the report.

This loop is what keeps the report honest: the model writes from data it queried out of
the run, not from its own priors. The system prompt is also primed with the
deterministic [story signals](./story-signals.md) — stakeholder positions, named
coalitions, the disagreement axis, phase boundaries, quotable posts, and simulation
scale — and instructs the model not to invent entities or events that aren't in that
data.

## What the report contains

The report is structured markdown with a fixed set of sections:

- **Executive Summary** — one paragraph answering the goal.
- **Verdict** — a single plain-language sentence, the headline result.
- **Key Findings** — exactly four findings, each tagged with a slot (industry,
  regulator, intermediary, market, or turning point) and citing the entities or quotes
  it rests on.
- **Agent Coalitions** — a prose description of the blocs that formed, anchored to
  phases ("early", "midway", "late") rather than raw round numbers.

After generation, the executive summary and the individual findings are parsed back out
of the markdown into structured fields, so the frontend can present them separately
while the full document remains available.

## Where it runs

Report generation happens off-pod, after the GPU running the simulation has been torn
down: the pod uploads its artifacts and releases, and a separate task then drives the
report LLM over those artifacts. The job is only marked complete once the report is
produced; any failure along the way fails the job rather than shipping a partial result.
