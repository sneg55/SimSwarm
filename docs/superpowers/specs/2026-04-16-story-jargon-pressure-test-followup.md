# Story Jargon Pressure-Test (Followup)

**Status:** Deferred — captured during the 2026-04-16 Story/Report redesign brainstorm, not to be addressed in that spec.

## Context

Our ICP is non-technical domain experts (policy analysts, fund managers, strategists). Story must survive a cold forwarded read — i.e. the recipient opens a Slack link from their boss without the buyer there to narrate. That surfaced several vocabulary items that leak engineer/researcher framing into user-facing surfaces and risk confusing or putting off cold readers.

This doc parks the decisions so they can be revisited after the Story/Report redesign ships.

## Terms to pressure-test

| Term | Where it shows | Concern | Candidate replacement |
|---|---|---|---|
| **Agent** | Finding cards, coalition cards, chat replay, landing copy | "AI agent" is mainstream but ambiguous in policy/markets contexts (secret service, estate agent). | Role-first language ("the finance-committee member") where a role is derivable; "simulated participant" as fallback. Keep "agent" in Report (analyst audience). |
| **Coalition** | Story cards, Report section header | Survives a cold read — in ordinary political/business vocabulary. | Keep, but always name the coalition by its stance ("the fiscal-hawk coalition") instead of generic "Coalition 1". |
| **Trajectory** | Data view, AgentTrajectoryChart | Engineering term. Non-technical readers may parse as "missile trajectory". | "Position over time" / "stance shift" / drop from Story; acceptable in Data view. |
| **Swarm / swarm intelligence** | Landing page, sometimes status copy | Evocative but can read as gimmicky for serious B2B buyers. | Consider "agent-based simulation" for credibility-sensitive surfaces. |
| **Tier** (e.g. "Deep tier") | Story header | Reads like a pricing concept next to substantive findings. | "Simulation depth: Deep" or drop from Story header. |
| **Round** | Previously in Story; already replaced | Internal bookkeeping unit, meaningless to ICP. | **Already decided** in parent brainstorm: replace with phase labels (Early/Mid/Late) + time units derived from `forecast_days`. "Round N" stays in Report for analyst audience. |

## What's already locked (from the parent brainstorm)

- **Round numbers removed from Story** — replaced with narrative phase + time-anchored language ("by week 2", "in the final week")
- **Coalitions named by stance, not generic** — part of the Path 3 deterministic-extraction spec
- `forecast_days` **required at sim creation** — so time-anchored language always grounds

## What's deferred

All other renames in the table above. Specifically:

1. Whether to replace "Agent" with role-first / "simulated participant" phrasing in Story surfaces
2. Whether to retire or reposition "Swarm / swarm intelligence" in customer-facing marketing copy
3. Whether to drop / rephrase "Tier" in the Story header
4. Whether to rename "Trajectory" in the Data view

Each is a small, self-contained copy change. None block the Story/Report redesign.

## Suggested next step when this is picked up

1. Customer-conversation validation — run the current Story copy past 3–5 ICP-shaped readers cold. Note where they pause, ask questions, or misparse.
2. Draft a small copy-rename spec that addresses the terms above in one pass, with before/after screenshots.
3. Align the landing-page / marketing copy with the Story copy so the vocabulary is coherent end-to-end.

## Links

- Parent brainstorm: [Story/Report redesign (2026-04-16)](#) — spec to be written at `docs/superpowers/specs/2026-04-16-story-report-redesign-design.md`
- Memory reference: "Target audience — non-technical domain experts who need zero-friction SaaS"
- Memory reference: "Differentiation — surface simulation-unique data; don't let output look like ChatGPT"
