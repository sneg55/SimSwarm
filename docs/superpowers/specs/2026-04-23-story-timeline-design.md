# Story Timeline — Design

Status: approved 2026-04-23
Scope: frontend only (`frontend/src/`)

## Goal

On the Simulation Results story view, map simulation rounds onto the user-selected forecast timeline (1 day → 1 year) and surface round-level "moments" on a horizontal band plus an upgraded vertical rail. Users should see *when* (on their real calendar) each finding, market move, coalition shift, or viral post happened.

## Inputs

From job payload (already shipped or trivially surfaceable):

- `startedAt` — `job.created_at` (sim creation timestamp)
- `horizonDays` — wizard value (verify field name during impl; likely `forecast_horizon_days`)
- `roundCount` — from results (`job.rounds` or `marketSeries[0].points.length`)
- `marketSeries` — derived markets with per-round probability points
- `stancePerRound` — stakeholder stance per round (from extraction)
- `posts` — extracted posts with engagement counts
- `findings` — structured report findings

## Round → Date Mapping

Uniform stretch:

```
roundDates[i] = start + i * (horizon_ms / (roundCount - 1))
start = startedAt
end   = start + horizonDays * 86400_000
```

Rounds are evenly spaced across the horizon. No engine changes; deterministic.

## Moment Types

Moment shape: `{ id, type, roundIndex, date, title, detail, refId }` where `type ∈ {market, coalition, post, finding}`.

- **market** — for each derived market, any round where `|Δprob| ≥ 15pp` vs prior round emits a moment.
- **coalition** — round-over-round diff of `stancePerRound`; emit when any stakeholder group flips stance or a new group crosses the formation threshold.
- **post** — top-engagement post per round, above a minimum floor to avoid noise.
- **finding** — each report finding pinned to the round where its supporting signal peaked; if no signal, pin to horizon midpoint.

All extraction runs client-side off data already present in the results payload.

## Components

### `frontend/src/composables/useSimTimeline.js` (new)

Pure function. Takes the inputs above, returns `{ start, end, roundDates[], moments[] }`. No Vue reactivity beyond what callers wrap it in. Fully unit-testable in isolation.

### `frontend/src/composables/useStoryScrollSync.js` (new)

Shared scroll-listener + active-round state. Both timeline components read/write the same state. Keeps scroll logic out of render components.

### `frontend/src/components/results/StoryTimelineBand.vue` (new)

Horizontal band, ~140px tall, mounted after `QuestionAnswerHero` and before `story-findings`.

- **Top row**: date axis with ticks at start, end, and 3–5 intermediate labels. Format adapts to horizon (hours for 1d, days for 1w/30d, weeks for 90d/6mo, months for 1y).
- **Middle**: moment lane. Dots colored by type — market=coral, coalition=ocean-teal, post=ocean-glow, finding=amber. Positioned at `(date - start) / horizon` as a % across the band.
- **Hover**: tooltip with title + date + one-line detail.
- **Click**: scrolls target element into view; briefly highlights it.
- **Bottom**: thin progress bar mirroring `activeIndex` from the rail.
- **Clustering**: pins within 2% horizontal distance collapse into a `+N` chip; click expands into a popover listing grouped moments.

Styling uses existing Tailwind palette tokens. No new charting library.

### `frontend/src/components/results/StoryTimeline.vue` (modified)

Add optional `moments` prop. Existing `sections`-only path preserved (other views unaffected).

When `moments` is passed:

- Date labels render next to major section dots (e.g., "Week 12").
- Small secondary dots injected between section dots, one per moment, color-coded by type.
- Scroll sync highlights both current section and nearest moment.

If the component starts mixing concerns, split render from scroll logic — scroll state already moves into `useStoryScrollSync.js`, so this should stay clean.

## Integration — `SimulationResults.vue`

Inside the `viewMode === 'story'` block:

```js
const timeline = useSimTimeline({
  startedAt, horizonDays, roundCount,
  marketSeries, stancePerRound, posts, findings,
})
```

Pass `timeline.moments` into both `StoryTimelineBand` (new, below hero) and the existing left-rail `StoryTimeline`. No prop drilling — shared state via `useStoryScrollSync`.

## Error & Empty States

- `roundCount < 2` → band renders nothing; rail falls back to current section-only behavior.
- Missing `horizonDays` → labels become "Round 1 … Round N" instead of dates; band still renders.
- No moments of a given type → that color simply doesn't appear.
- Click target element missing → silent no-op.

## Testing

- `useSimTimeline.spec.js` — mapping math (incl. 2-round edge case), each moment extraction rule, clustering math.
- `StoryTimelineBand.spec.js` — correct pin count, cluster behavior, `select` event on click, graceful degrade when a moment type is empty.
- `StoryTimeline.spec.js` — extend existing spec to cover the new `moments` path without regressing the section-only path.
- No backend tests — no backend changes.

## Out of Scope (v1)

- Per-round enrichment events (requires engine work — today enrichment only runs once at sim start).
- Agent-authored in-world dates parsed from LLM output.
- Post-hoc editing or annotating the timeline.
- Exporting the timeline as an image.

## Open Verification Items (resolve during implementation)

- Exact field name for the horizon on the job row (`forecast_horizon_days` vs other). Check `saas/jobs/models.py` and `export.py`.
- Whether `stancePerRound` is already exposed in the results API or only inside MinIO extraction artifacts. If the latter, surface it in the results payload rather than fetching raw artifacts client-side.
