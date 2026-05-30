---
sidebar_label: Story Signals
---

# Story signals

Story signals are a set of deterministic, structured summaries extracted from a
finished simulation. They turn the raw chat log and entity graph into a small,
readable picture of what happened: who took which side, how the run unfolded over
time, and which moments mattered. The same signals feed both the Story result view and
the grounding context the [report](./reports.md) is written from, so the narrative and
the report describe the same underlying run.

Story signals are computed by pure functions, with no LLM calls and no external I/O, so
they are reproducible from the simulation artifacts.

## What the signals measure

- Stakeholder positions: agents are clustered by their dominant stance across all
  their posts (opposed, supportive, neutral, or split). Each cluster lists its members,
  its size, and the keywords that characterize its rationale.
- Named coalitions: stakeholder clusters with two or more members are promoted to
  named groups, so blocs that actually formed get a label rather than just a stance.
- Disagreement axis: the single line of contention the run was organized around,
  expressed as the top theme on the supportive side versus the top theme on the opposed
  side (stance words themselves are filtered out so the axis reflects substance, not just
  "support vs oppose").
- Phase boundaries: the run is split into early / mid / late phases (or a single
  "full horizon" for very short runs), each tagged with its dominant topic and the
  calendar week range it maps to on your forecast horizon.
- Quotable posts: the highest-engagement post per phase per stance, deduplicated so
  the same agent isn't quoted twice. These are the lines that carried the conversation.
- Simulation scale: aggregates about the run, including how many participants took
  part, the horizon in days, the number of blocs, and whether any market stress was
  actually observed (rather than implied).

## How to read them

Read the signals as the *shape* of the simulation. Start with the disagreement axis and
named coalitions to see what the population split over and how it organized; walk the
phase boundaries to see how the dominant topic moved early to late; and use the quotable
posts as concrete evidence behind each phase. The simulation-scale figures tell you how
much weight to give the result, such as whether market stress was genuinely
present or simply not observed.

Because every signal is derived directly from what the agents did, nothing here is
invented: a coalition, axis, or quote always traces back to real posts in the run.
