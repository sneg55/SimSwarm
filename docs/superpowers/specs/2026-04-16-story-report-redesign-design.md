# Story / Report Redesign — Deterministic Signals First

**Date:** 2026-04-16
**Status:** Spec approved in brainstorming session. Plan next.
**Parent followup:** [`2026-04-16-story-jargon-pressure-test-followup.md`](2026-04-16-story-jargon-pressure-test-followup.md)

## Problem

`SimulationResults.vue` has four view modes (Story, Graph, Data, Report). Story and Report both render the same `job.result_report` markdown through `ReportViewer`. Story wraps it in a few structured cards; Report adds a `ChatReplay` below. **The core body content is identical** — which means both views look like reformatted ChatGPT output and fail our explicit differentiation principle ("Surface simulation-unique data; don't let output look like ChatGPT").

The `structured` fields that feed Story's cards are thin or mislabeled:
- `findings` often contains only 1 item despite the prompt asking for 2–5.
- `coalitions` is empty for most real jobs (mutual-follow heuristic misses thematic alignment — e.g., prod job #109 had obvious "industry bloc" / "regulator bloc" dynamics but detection returned `[]`).
- `sentiment` is a keyword heuristic that returns `value: 0` in practice.
- `confidence` is actually a sim-scale count (Agents / Rounds / Entities / Trades), not a confidence signal. Non-technical recipients misread it.
- `key_insight` is regex-extracted and in prod is leaking LLM scratchpad text ("I now have comprehensive data across all key agents. Let me compile the final report.").

## ICP shape

Non-technical domain experts — policy analysts, fund managers, strategists. **Story must survive a cold forwarded read** (buyer forwards a link to their boss; boss opens it cold without narration). That forces:

1. Self-contained cards — no "as shown above" references.
2. Context up top every time — what was simulated, for whom, over what horizon.
3. Visible provenance — "this came from a simulation, not a chatbot" readable in ~3 seconds.
4. Domain-language — no engineer vocabulary ("rounds", "trajectory", "belief curve") leaking into Story.

Report, by contrast, serves the analyst cohort (the buyer re-reading, or someone challenging a conclusion). That audience tolerates markdown and round numbers.

## Direction

- **Story** = share artifact. Q+A hero, stakeholder chips, 2×2 finding deck, sim-scale footer, share bar.
- **Report** = reference document. **Unchanged.** Markdown + `ChatReplay` + sources. No visual redesign in this spec.

## Pipeline: deterministic signals first, LLM prose consumes them

Two complementary stages. The key design decision is that **deterministic extraction runs first and its outputs are passed to the LLM prompt as grounding**. This collapses hallucination risk and ensures every claim in Story is traceable to a real simulation signal.

### Path 3 — Deterministic extraction from chat_log + graph_data

Pure-Python aggregation. No LLM calls. Runs in milliseconds after `_load_job_artifacts` returns.

New module: `simswarm/story_signals.py`

Produces a dict merged into `result_structured`:

```python
{
    # Deterministic signals (Path 3)
    "stakeholder_positions": [
        # Agents grouped by final stance, derived from their posts/trades.
        {
            "name": "Industry bloc",           # labeled by shared stance keywords
            "stance": "opposed",               # supports | opposed | neutral | split
            "members": ["Morgan Stanley", "Microsoft", ...],
            "member_count": 6,
            "rationale_keywords": ["adaptable frameworks", "industry-led"],
        },
    ],
    "disagreement_axis": "prescriptive mandates vs industry-led frameworks",
    "quotable_posts": [
        {
            "agent_name": "Morgan Stanley",
            "agent_role": "bank",              # derived from graph entity type if present
            "phase": "Early",
            "text": "…",
            "engagement": 42,                  # likes + reposts
        },
    ],
    "named_coalitions": [
        # Replaces current `coalitions` — named by stance/topic, not generic "Coalition 1".
        {"name": "Industry alignment bloc", "members": [...], "size": 6, "stance": "opposed"},
        {"name": "Transparency bloc", "members": ["SEC", "Investor Advisory Committee"], "size": 2, "stance": "firm"},
    ],
    "phase_boundaries": [
        # Rounds chunked into thirds, time-anchored via forecast_days.
        {"phase": "Early", "rounds": [1, 5], "week_range": "Weeks 1-2", "dominant_topic": "compliance costs"},
        {"phase": "Mid", "rounds": [6, 10], "week_range": "Week 3", "dominant_topic": "regulator pushback"},
        {"phase": "Late", "rounds": [11, 15], "week_range": "Week 4", "dominant_topic": "Fed intermediation"},
    ],
    "sim_scale": {
        "participants": 10,
        "horizon_days": 30,
        "bloc_count": 2,
        "market_stress": "none_observed",       # none_observed | present | unclear
        # Derivation: market_stress = "present" if trade volume > baseline, else "none_observed".
    },
    # LLM-authored narrative (Path 2, below)
    "verdict": "…one-sentence domain-language answer…",
    "brief": "…",
    "findings": [ … 4 findings mapped to stakeholder/phase/market slots … ],
}
```

**Removed from `result_structured`:**
- `sentiment` — unreliable keyword heuristic, not salvageable. Delete.
- `confidence` in its current shape — replaced by `sim_scale` with honest labels.

### Path 2 — LLM prose grounded in Path 3

`simswarm/prompts/report.j2` rewritten to receive Path 3 signals as context. The prompt shifts from "write a generic report" to "given these computed signals, write a one-sentence verdict and 4 findings mapped to specific slots."

New prompt contract:
- Input: `goal`, `forecast_days`, plus the full Path 3 dict.
- Output: still markdown in the same structure Report uses (`## Executive Summary`, `## Key Findings`, etc.) — so Report view is unchanged — but every claim must cite entities or phases from Path 3.
- Additional structured fields in the final response: `verdict` (one sentence), and exactly 4 findings each tagged `industry | regulator | intermediary | market | turning_point` (Story renders whichever 4 slots the job produced).

Because the LLM receives computed structure, it cannot invent entities or turning points that aren't in the simulation — and produces prose that reads as analysis of *this* sim, not a generic policy summary.

## Frontend: Story page redesign

New layout in `frontend/src/views/SimulationResults.vue` for `viewMode === 'story'`. Approved visual direction is captured in the prod-data mockup at `.superpowers/brainstorm/.../story-cd-real.html` (kept in repo for reference during implementation).

Section order top-to-bottom:

1. **ResultsToolbar** — unchanged. Keeps Story/Graph/Report/Data toggle.
2. **Meta row** — mono-font label strip: `Simulation · {participants} participants · {horizon_days}d horizon · {tier} depth`.
3. **Hero card (Q+A)**
   - "The question" label (coral-amber) + `job.goal` verbatim as H2.
   - "Simulated answer" label (ocean-glow) + `verdict` paragraph with named entities bolded, key phrases emphasized.
   - Stakeholder chip row — one chip per `stakeholder_positions` entry, stance-coded:
     - `opposed` → coral-amber
     - `firm` / `supports` → ocean-glow
     - `neutral` / `intermediary` → organic-violet
     - `split` → organic-violet with split styling
4. **"What the simulation surfaced"** section label + **2×2 finding deck**
   - Each card: accent stripe (color-coded by slot), mono-font label, title, body, citation line.
   - 4 cards total, one per Path 2 slot when available. If fewer than 4 slots populate (small sims), render the available cards full-width in a single column.
5. **Sim-footer** — four stat tiles: `{participants}` · `{horizon_days}d` · `{bloc_count}` blocs · market stress state.
6. **Share bar** — copy-link / export-PDF buttons. Includes provenance note: *"This artifact was generated by a multi-agent simulation. Open the Report for methodology and source citations."*

### Removed from Story

- `ReportViewer` (raw markdown) — moved to Report only.
- `ConfidenceGrid` component — replaced by sim-footer.
- `SentimentBars` component — deleted (backs `sentiment` field that's going away).
- Current `MarketCurveCompact` / `EngagementCompact` compact widgets — dropped from Story (they add noise for the cold-forward reader). They remain available in Data view, where analysts expect them.
- `enriched_seed` card — moves to Report's "Sources & Background" section.

### Palette / typography

Actual product tokens from `tailwind.config.js`. No new colors:
- Backgrounds: `ocean-abyss` (body), `ocean-deep` (cards).
- Text: `mist-foam` (primary), `mist` (secondary), `mist-drift` (tertiary), `mist-slate` (meta).
- Accents: `ocean-glow` (answer/regulator), `coral-amber` (question label/industry), `organic-violet` (intermediary), `organic-seafoam` (market).
- Borders: `mist-depth`.
- Type: Inter for body, JetBrains Mono for labels and citations.

## Frontend: Report page — unchanged

No design work. Stays as-is: markdown (`ReportViewer`) + `ChatReplay` + sources + header. Analyst audience is well-served today, and Report already didn't render the `structured`-driven cards — those lived in Story only.

## API: `forecast_days` required

Today `forecast_days` is `Optional[int]` on `JobCreate` and nullable in `SimulationJob`. Make it required for new jobs:

- `saas/jobs/schemas.py::JobCreate.forecast_days: int` (no `| None`).
- Launch validation in `launchDraft` — reject with 422 if draft has `forecast_days is None`.
- Draft creation still allows null (drafts are scratchpads).
- Wizard preselects a default chip in `TimelineChips.vue` (30 days — category-generic fit).
- DB column stays nullable; no backfill (legacy jobs explicitly out of scope per alignment call).
- Story rendering assumes `forecast_days` is always present for new jobs. Legacy jobs that hit Story will render without the time layer in phase labels.

## Backend structure

New:
- `simswarm/story_signals.py` — pure functions: `extract_stakeholder_positions`, `extract_quotable_posts`, `name_coalitions`, `extract_phase_boundaries`, `compute_sim_scale`, plus a top-level `build_story_signals(chat_log, graph_data, forecast_days) -> dict`.

Modified:
- `simswarm/adapter.py::adapt_structured` — delegate to `build_story_signals`; remove `_compute_platform_sentiment` (and its call); rename `_build_confidence` → `_build_sim_scale` with new fields; coalition naming moves to `story_signals.name_coalitions`.
- `simswarm/prompts/report.j2` — new prompt consuming Path 3 context (verdict + 4-slot findings).
- `saas/jobs/report.py` — build Path 3 dict before constructing `ReportRunner`; pass into system prompt template; parse new structured fields from final LLM response (`verdict`, slotted findings).
- `saas/jobs/tasks_report.py::_build_structured` — merge Path 3 dict + LLM `verdict` / `findings` into final `result_structured` JSON.
- `saas/jobs/persistence.py::_extract_key_insight` — replaced. `key_insight` sourced from the Path 2 `verdict` field directly, removing the regex-based scratchpad-leak bug (job #109 currently stores "I now have comprehensive data across all key agents. Let me compile the final report." as `key_insight`).
- `saas/jobs/schemas.py` — `forecast_days: int` required on `JobCreate`.
- `frontend/src/composables/useSimulationData.js` — expose new signals (stakeholder_positions, named_coalitions, phase_boundaries, sim_scale, verdict). Remove `sentimentBars` computed.
- `frontend/src/views/SimulationResults.vue` — replace Story block with the new layout; simplify Report block (still renders `ReportViewer` + `ChatReplay` + sources, no `structured`-driven cards).
- `frontend/src/components/results/` — new `QuestionAnswerHero.vue`, `StakeholderChip.vue`, `FindingSlotCard.vue`, `SimScaleFooter.vue`. Delete `SentimentBars.vue`, `ConfidenceGrid.vue` (sim-footer replaces it), `EngagementCompact.vue`, `MarketCurveCompact.vue` from Story (may remain in Data view).
- `frontend/src/components/wizard/WizardGoal.vue` (or wherever `TimelineChips` is mounted) — set default `modelValue` to `30` on first render.

Deleted:
- `SentimentBars.vue` (Story surface) — Data view retains its own sentiment visualizations if any.
- `_compute_platform_sentiment` in `simswarm/adapter.py`.

## Testing

- Unit tests per Path 3 function in `tests/engine/test_story_signals.py` — fixture-based, deterministic.
- Regression test using prod job #109's `chat_log` (sanitized fixture): assert `named_coalitions` surfaces Industry + Transparency blocs even though current mutual-follow detection returns `[]`.
- Snapshot test for `SimulationResults.vue` Story mode.
- E2E: create job with `forecast_days` required → run → confirm Story renders all expected sections.
- Prompt regression: mock Anthropic client, verify `report.j2` consumes Path 3 context correctly and returns expected `verdict` + 4 findings.

## Out of scope

- Jargon pressure-test (see parent followup doc).
- Report visual redesign.
- Data view changes.
- Graph view changes.
- Backfill of legacy jobs.
- Changes to `enrich_web` / seed enrichment pipeline.
- PDF export template updates (sep pass once Story layout lands).

## Open for plan phase

1. **Stakeholder-position clustering algorithm.** Count-based (shared follow targets)? Keyword-based (TF-IDF over posts)? Hybrid? Needs a small design call in the plan, probably both with a simple stance-override heuristic.
2. **Phase granularity.** Thirds always, or halves for very short sims (<10 rounds)? Probably thirds; document the decision.
3. **Quote selection algorithm.** Top-engagement per phase per stance? Risk of picking the same agent repeatedly. Plan should pick one rule and note the trade-off.
4. **Market-stress derivation.** Baseline for "above baseline" needs a concrete definition — e.g., `trade_count_per_round > μ + σ` of historical jobs, or simply `trade_count > 0`. Recommend the latter for v1.
5. **Fewer-than-4-findings fallback layout.** Plan should specify the 1-card / 2-card / 3-card layouts.
6. **Path 3 without Path 2 (interim ship).** Backend can ship Path 3 and have Story render its raw outputs (minus `verdict`) before the prompt rewrite lands. Plan should decide whether to stage or ship together.

## References

- Brainstorm transcript (this session).
- Memory: *Differentiation* — "Surface simulation-unique data; don't let output look like ChatGPT."
- Memory: *Target audience* — "Non-technical domain experts who need zero-friction SaaS."
- Memory: *Visual identity* — "Ocean teal, coral accents, bioluminescent glows, fluid animations."
- Prod reference job: #109 (SEC AI disclosure rules, 30-day horizon).
- Approved mockup: `.superpowers/brainstorm/89817-1776353393/content/story-cd-real.html` (prod-data C+D, product palette).
