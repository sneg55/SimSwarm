# Story Signals Classifier Tuning (Followup)

**Status:** Deferred — captured during Task 9 review of the 2026-04-16 Story/Report redesign. The pipeline is functional and the job #109 regression passes honestly. These are signal-quality concerns that should be addressed before Story cards ship to end users, but do not block the rest of the implementation plan.

## Context

Task 9 added a prod-data regression using job #109 (SEC AI disclosure rules). Getting `build_story_signals` to return ≥2 named coalitions on real data required widening `OPPOSED_SIGNALS` / `SUPPORT_SIGNALS` keyword sets and rewriting `_classify_stance` from binary to count-and-dominate. The regression passes (2 coalitions surfaced), but three quality concerns surfaced that should be addressed in a follow-up pass.

## Followup 1 — SEC-in-opposed-bloc misclassification

On job #109, the full pipeline currently produces:

```
opposed (8): Financial Services Forum, Goldman Sachs, Google, JPMorgan Chase,
             Meta, Microsoft, Morgan Stanley, SEC
supports (2): Investor Advisory Committee, Jerome Powell
```

SEC is the body that **wrote** the rules being debated — grouping it with the industry bloc opposing them is wrong. The root cause: SEC's posts are genuinely bridging ("balance transparency with innovation") and echo industry framing (`proprietary`, `adaptive frameworks`, `stifling progress`) while actually defending the rules. The count-and-dominate classifier sees more OPPOSED keyword hits and ships SEC into the opposed bucket.

**Impact:** The Story finding cards and coalition names will mislead users if this ships as-is.

**Candidate fixes:**
1. Promote "bridging/balancing" to a first-class stance label (requires new logic + bucket + chip style).
2. Weight classification by **post-level aggregation** rather than sentence-level hits (a post that says "while X, Y" should weight Y, not X).
3. Use **agent role/identity** from graph labels (e.g., `RegulatoryBody`, `Bank`, `TechFirm`) as a tiebreaker when keyword-based classification is ambiguous.
4. Detect concession phrases (`while industry concerns are valid`, `balance X with Y`) and strip the conceded clause before classification.

Recommended investigation order: #3 (cheapest), then #4, then #2, with #1 as the last-resort structural change.

## Followup 2 — Keyword set pruning

Task 9 added 26 keywords. Asymmetry spot-check revealed:

**Dead keywords (zero fixture hits — should be removed):**
- `OPPOSED_SIGNALS`: `undue burden`
- `SUPPORT_SIGNALS`: `oversight`, `robust`

**Inverted keywords (flagged for wrong bloc):**
- `OPPOSED_SIGNALS`: `hinder` (2 industry / 4 regulator), `regulatory fragmentation` (1 industry / 4 regulator)
- `SUPPORT_SIGNALS`: `investor protection` (3 industry / 1 regulator), `investor confidence` (6 industry / 1 regulator) — industry is co-opting investor-protection framing

**Symmetric keywords (used equally by both blocs):**
- `SUPPORT_SIGNALS`: `ensure transparency` (6 / 6), `systemic resilience` (19 / 16)

**Near-symmetric (worth reviewing):**
- `OPPOSED_SIGNALS`: `stifle` (6 / 5), `stifling` (18 / 15)

**Action:** remove dead keywords, flip inverted ones, and decide whether to drop or keep symmetric ones (they add noise without signal).

## Followup 3 — Action-type normalization DRY

Task 9's fix added `action.get("action_type", "").lower() in (...)` at six call sites across `simswarm/story_signals.py` and `simswarm/story_signals_scale.py`. The same pattern exists elsewhere (`simswarm/report_tools.py`, `saas/jobs/report_tools_minio.py`, `simswarm/extractor_common.py`).

**Action:** extract a `normalize_action_type(action) -> str` helper in `simswarm/extractor_common.py` (where `post_text` already lives), and replace the six call sites. Single invariant, grep-able.

## What's already locked (not deferred)

- Action-type case-insensitive comparison — already shipped in Task 9.
- Trade-success gating in `compute_sim_scale` — already shipped.
- Trade types include `buy_shares`/`sell_shares` — already shipped.
- Count-and-dominate classifier — already shipped.

## Suggested sequencing

1. After the full plan ships (Tasks 1-24), run the pipeline against 3-5 additional prod jobs (not just #109) and inventory misclassifications per Followup 1.
2. Prune keyword set (Followup 2) based on the wider corpus.
3. DRY the action-type helper (Followup 3) as part of the next codebase-hygiene pass.
4. Revisit the classifier architecture only if keyword pruning + identity-tiebreaker (Followup 1 option 3) don't resolve SEC-class cases.

## Links

- Parent spec: [2026-04-16-story-report-redesign-design.md](2026-04-16-story-report-redesign-design.md)
- Parent plan: [docs/superpowers/plans/2026-04-16-story-report-redesign.md](../plans/2026-04-16-story-report-redesign.md)
- Companion followup on vocabulary: [2026-04-16-story-jargon-pressure-test-followup.md](2026-04-16-story-jargon-pressure-test-followup.md)
- Regression source: job #109 fixture at `tests/engine/fixtures/job_109_chat_log.json`
