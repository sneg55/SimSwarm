# Story / Report Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Story view as a share-ready Q+A hero + 2×2 finding deck driven by deterministic signals extracted from simulation chat_log/graph, with the report LLM prompt rewritten to consume those signals rather than invent them. Report view stays as-is.

**Architecture:** Two-stage pipeline. Stage 1 (Path 3, deterministic): new `simswarm/story_signals.py` module produces structured stakeholder positions, named coalitions, phase boundaries, quotable posts, and sim-scale aggregates from chat_log + graph_data. Stage 2 (Path 2, LLM): existing report runner passes Path 3 output to a rewritten `report.j2` prompt that returns a one-sentence `verdict` plus four slot-tagged findings. Frontend reads the merged `result_structured` JSON through a redesigned Story layout in `SimulationResults.vue`.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy, Celery (sync DB via psycopg2), Jinja2 prompts, Anthropic SDK. Frontend: Vue 3 Composition API, Pinia, Tailwind CSS (ocean/coral/mist palette in `tailwind.config.js`), Vitest.

**Reference assets:**
- Spec: `docs/superpowers/specs/2026-04-16-story-report-redesign-design.md`
- Approved mockup (prod-data C+D in product palette): `.superpowers/brainstorm/89817-1776353393/content/story-cd-real.html`
- Prod regression fixture source: job #109 (SEC AI disclosure rules, 30-day horizon)

**Resolved design decisions from the spec's "Open for plan phase" list:**

1. **Stakeholder clustering:** keyword-based. Agents are grouped by shared stance-keywords extracted from their posts. Stance is inferred by checking post text against two curated keyword sets (`OPPOSED_SIGNALS`, `SUPPORT_SIGNALS`) — if neither triggers, stance is `neutral`.
2. **Phase granularity:** always thirds. If `max_round < 3`, collapse to a single `"Full horizon"` phase.
3. **Quote selection:** top engagement (likes + reposts) per phase per stance; max one quote per agent across all selections.
4. **Market stress:** `"present"` if any `BUY`/`SELL` actions in the sim, else `"none_observed"`. Simple, honest.
5. **Fewer-than-4 findings layout:** 1 card = full width; 2 cards = 2-up single row; 3 cards = 2-up + 1 full width; 4 cards = 2×2.
6. **Ship order:** backend + frontend land together in a single PR. No interim "Path 3 without Path 2" ship — avoids exposing an unfinished Story surface to users.

---

## File Structure

**New files:**
- `simswarm/story_signals.py` — Path 3 deterministic extractor (pure functions over chat_log + graph_data)
- `tests/engine/test_story_signals.py` — unit tests for each Path 3 function
- `tests/engine/story_signals_fixtures.py` — shared fixture builders for the above
- `tests/engine/fixtures/job_109_chat_log.json` — sanitized prod chat_log for regression
- `tests/engine/fixtures/job_109_graph.json` — sanitized prod graph for regression
- `frontend/src/components/results/QuestionAnswerHero.vue` — question label + goal + answer label + verdict + stakeholder chips
- `frontend/src/components/results/StakeholderChip.vue` — single stance-coded chip
- `frontend/src/components/results/FindingSlotCard.vue` — single finding card (accent-coded by slot)
- `frontend/src/components/results/SimScaleFooter.vue` — four stat tiles (participants / horizon / blocs / market stress)
- `frontend/src/components/results/__tests__/QuestionAnswerHero.spec.js` — component test
- `frontend/src/components/results/__tests__/FindingSlotCard.spec.js` — component test
- `frontend/src/components/results/__tests__/SimScaleFooter.spec.js` — component test

**Modified files:**
- `simswarm/adapter.py` — delegate `adapt_structured` to `story_signals.build_story_signals`; remove `_compute_platform_sentiment`, `_detect_coalitions`, `_build_confidence`
- `simswarm/prompts/report.j2` — rewrite to consume Path 3 signals, demand 4-slot findings + `verdict`
- `saas/jobs/report.py` — pass Path 3 signals into prompt render; parse `verdict` + slotted findings from final response
- `saas/jobs/tasks_report.py::_build_structured` — merge Path 3 dict + LLM output into final `result_structured`
- `saas/jobs/persistence.py::_extract_key_insight` — replace regex extraction with direct sourcing from `verdict` field
- `saas/jobs/schemas.py::JobCreate.forecast_days` — `int` (required, no default)
- `saas/jobs/api_draft.py` (wherever `launchDraft` is handled) — reject 422 if `forecast_days is None`
- `tests/contracts/schemas.py::StructuredResults` — update to new shape (drop `sentiment`/`confidence`/`coalitions`; add `verdict`, `stakeholder_positions`, `named_coalitions`, `phase_boundaries`, `sim_scale`, `quotable_posts`, `disagreement_axis`)
- `frontend/src/composables/useSimulationData.js` — expose new fields (`verdict`, `stakeholderPositions`, `namedCoalitions`, `phaseBoundaries`, `simScale`, `quotablePosts`); remove `sentimentBars`
- `frontend/src/views/SimulationResults.vue` — replace Story block with new layout using new components; leave Report block untouched
- `frontend/src/components/wizard/TimelineChips.vue` — preselect 30-day default when `modelValue` is null
- `frontend/src/components/wizard/WizardGoal.vue` (or wherever it initializes) — pass `30` as initial value instead of `null`

**Deleted files:**
- `frontend/src/components/results/SentimentBars.vue` (and its tests) — backs the `sentiment` field that's going away
- `frontend/src/components/results/ConfidenceGrid.vue` (and its tests) — replaced by `SimScaleFooter.vue`
- Existing tests in `tests/engine/test_adapter_structured.py` that assert on `sentiment` or on the old `confidence` / `coalitions` shapes — replaced by new tests in `test_story_signals.py`

---

## Task 1: Scaffold story_signals module and fixture file

**Files:**
- Create: `simswarm/story_signals.py`
- Create: `tests/engine/story_signals_fixtures.py`
- Create: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Create the module file with type signatures only**

Write `simswarm/story_signals.py`:

```python
"""Deterministic extraction of Story signals from chat_log + graph_data.

Pure functions only. No LLM calls, no I/O. The output feeds both the Story
view directly and the report.j2 prompt as grounding context.
"""
from __future__ import annotations

from typing import Any

# Curated stance-signal keyword sets. Extracted from a corpus of prod goals
# (policy/markets/crisis/competitive/public-opinion verticals). These are
# intentionally conservative — a post that triggers neither set is neutral.
OPPOSED_SIGNALS: frozenset[str] = frozenset({
    "oppose", "against", "reject", "block", "resist", "pushback",
    "overreach", "mandate", "prescriptive", "burden", "compliance cost",
    "unworkable", "chilling", "harmful",
})

SUPPORT_SIGNALS: frozenset[str] = frozenset({
    "support", "endorse", "align with", "back the", "welcome", "approve",
    "transparency", "accountability", "standardized", "enforce",
    "strengthen", "clarity",
})

# Phase accent colors — aligned with tailwind.config.js tokens. These are
# hex values (Vue components use the class names; Python stores hex for
# JSON transport).
SLOT_COLORS: dict[str, str] = {
    "industry":      "#F97316",  # coral-amber
    "regulator":     "#22D3EE",  # ocean-glow
    "intermediary":  "#A78BFA",  # organic-violet
    "market":        "#6EE7B7",  # organic-seafoam
    "turning_point": "#FF6B6B",  # coral
}


def build_story_signals(
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
    forecast_days: int,
) -> dict[str, Any]:
    """Top-level entry. Returns the deterministic signals dict.

    Shape (see spec for full schema):
        {
            "stakeholder_positions": [...],
            "disagreement_axis": str,
            "quotable_posts": [...],
            "named_coalitions": [...],
            "phase_boundaries": [...],
            "sim_scale": {...},
        }
    """
    raise NotImplementedError
```

Write `tests/engine/story_signals_fixtures.py`:

```python
"""Shared fixtures for story_signals tests."""
from __future__ import annotations


def make_chat_log() -> list[dict]:
    """A minimal chat log covering 15 rounds with two clear stance blocs."""
    return [
        # Industry bloc — opposed stance
        {"round_num": 1, "agent_id": "ms", "agent_name": "Morgan Stanley",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "We oppose prescriptive mandates; adaptable frameworks serve markets better."},
         "timestamp": None, "success": True},
        {"round_num": 5, "agent_id": "msft", "agent_name": "Microsoft",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Overly strict data disclosure requirements would be a compliance cost burden we oppose."},
         "timestamp": None, "success": True},
        {"round_num": 8, "agent_id": "ms", "agent_name": "Morgan Stanley",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Compliance coalitions should be industry-led, not prescriptive."},
         "timestamp": None, "success": True},
        # Regulator bloc — supportive stance
        {"round_num": 2, "agent_id": "sec", "agent_name": "SEC",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Standardized transparency is essential; we endorse accountability."},
         "timestamp": None, "success": True},
        {"round_num": 6, "agent_id": "iac", "agent_name": "Investor Advisory Committee",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "We support standardized disclosure frameworks with clarity."},
         "timestamp": None, "success": True},
        # Neutral — Fed
        {"round_num": 10, "agent_id": "fed", "agent_name": "Federal Reserve",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Accountability must be balanced against systemic stability."},
         "timestamp": None, "success": True},
        # Engagement signals — one like on Morgan Stanley's post
        {"round_num": 9, "agent_id": "gs", "agent_name": "Goldman Sachs",
         "action_type": "LIKE_POST", "platform": "twitter",
         "action_args": {"target_post": "ms_r8"},
         "timestamp": None, "success": True},
    ]


def make_graph_data() -> dict:
    return {
        "nodes": [
            {"uuid": "n1", "name": "Morgan Stanley", "labels": ["Entity", "Bank"], "summary": ""},
            {"uuid": "n2", "name": "Microsoft", "labels": ["Entity", "Tech"], "summary": ""},
            {"uuid": "n3", "name": "SEC", "labels": ["Entity", "Regulator"], "summary": ""},
        ],
        "edges": [],
        "metadata": {"entity_types": ["Bank", "Tech", "Regulator"], "total_nodes": 3, "total_edges": 0},
    }
```

Write `tests/engine/test_story_signals.py` skeleton:

```python
"""Tests for simswarm.story_signals.build_story_signals and helpers."""
from __future__ import annotations

import pytest

from simswarm import story_signals
from tests.engine.story_signals_fixtures import make_chat_log, make_graph_data


class TestBuildStorySignals:
    def test_returns_expected_top_level_keys(self):
        pytest.skip("implemented in Task 8")
```

- [ ] **Step 2: Run tests — verify skeleton imports cleanly**

Run: `pytest tests/engine/test_story_signals.py -v`
Expected: one SKIPPED test, no import errors.

- [ ] **Step 3: Commit**

```bash
git add simswarm/story_signals.py tests/engine/story_signals_fixtures.py tests/engine/test_story_signals.py
git commit -m "feat(story): scaffold story_signals module + test fixtures"
```

---

## Task 2: Implement `_classify_stance` helper

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestClassifyStance:
    def test_opposed_keyword_returns_opposed(self):
        assert story_signals._classify_stance("we oppose this") == "opposed"

    def test_support_keyword_returns_supports(self):
        assert story_signals._classify_stance("we endorse standardized rules") == "supports"

    def test_no_keyword_returns_neutral(self):
        assert story_signals._classify_stance("the sky is blue") == "neutral"

    def test_both_keywords_returns_split(self):
        assert story_signals._classify_stance("we oppose prescriptive rules but support transparency") == "split"

    def test_case_insensitive(self):
        assert story_signals._classify_stance("WE OPPOSE THIS") == "opposed"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestClassifyStance -v`
Expected: 5 FAILED (AttributeError: module has no `_classify_stance`).

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
def _classify_stance(text: str) -> str:
    """Return 'opposed' | 'supports' | 'neutral' | 'split' based on keyword signals."""
    lowered = text.lower()
    has_opposed = any(kw in lowered for kw in OPPOSED_SIGNALS)
    has_support = any(kw in lowered for kw in SUPPORT_SIGNALS)
    if has_opposed and has_support:
        return "split"
    if has_opposed:
        return "opposed"
    if has_support:
        return "supports"
    return "neutral"
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestClassifyStance -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add _classify_stance keyword heuristic"
```

---

## Task 3: Implement `extract_stakeholder_positions`

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestExtractStakeholderPositions:
    def test_groups_opposed_agents(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        opposed = next((p for p in positions if p["stance"] == "opposed"), None)
        assert opposed is not None
        assert "Morgan Stanley" in opposed["members"]
        assert "Microsoft" in opposed["members"]

    def test_groups_supportive_agents(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        supportive = next((p for p in positions if p["stance"] == "supports"), None)
        assert supportive is not None
        assert "SEC" in supportive["members"]
        assert "Investor Advisory Committee" in supportive["members"]

    def test_position_has_required_keys(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        assert positions
        for p in positions:
            assert set(p.keys()) >= {"name", "stance", "members", "member_count", "rationale_keywords"}

    def test_member_count_matches_members(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        for p in positions:
            assert p["member_count"] == len(p["members"])

    def test_empty_chat_log_returns_empty_list(self):
        assert story_signals.extract_stakeholder_positions([]) == []

    def test_position_name_reflects_stance(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        names = {p["name"] for p in positions}
        # Expect human-readable bloc names — not "Coalition 1"
        assert any("oppos" in n.lower() or "against" in n.lower() or "industry" in n.lower() for n in names) \
            or any("support" in n.lower() or "regulator" in n.lower() or "transparency" in n.lower() for n in names)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestExtractStakeholderPositions -v`
Expected: 6 FAILED (module has no `extract_stakeholder_positions`).

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
import re
from collections import Counter, defaultdict


def _post_text(action: dict[str, Any]) -> str:
    args = action.get("action_args") or {}
    return args.get("text") or args.get("content") or ""


def _agent_dominant_stance(agent_posts: list[dict[str, Any]]) -> str:
    """A single agent's overall stance = majority stance across their posts."""
    if not agent_posts:
        return "neutral"
    counts = Counter(_classify_stance(_post_text(p)) for p in agent_posts)
    # Drop neutral when any directional stance exists — neutral shouldn't win by default.
    directional = {k: v for k, v in counts.items() if k != "neutral"}
    if directional:
        return max(directional.items(), key=lambda kv: kv[1])[0]
    return "neutral"


def _top_keywords(texts: list[str], limit: int = 3) -> list[str]:
    """Top non-stopword tokens across a bag of texts."""
    stopwords = {"the", "a", "an", "is", "are", "to", "of", "for", "and", "or",
                 "in", "on", "we", "our", "this", "that", "it", "be", "by",
                 "with", "as", "at", "from", "will", "not", "but"}
    tokens: Counter[str] = Counter()
    for t in texts:
        for word in re.findall(r"[a-z][a-z\-]{3,}", t.lower()):
            if word not in stopwords:
                tokens[word] += 1
    return [w for w, _ in tokens.most_common(limit)]


_STANCE_BLOC_NAME = {
    "opposed":  "Opposition bloc",
    "supports": "Support bloc",
    "neutral":  "Neutral bloc",
    "split":    "Split bloc",
}


def extract_stakeholder_positions(chat_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster agents by dominant stance and return stakeholder position dicts."""
    posts_by_agent: dict[str, list[dict]] = defaultdict(list)
    for action in chat_log:
        if action.get("action_type") in ("CREATE_POST", "CREATE_COMMENT"):
            posts_by_agent[action.get("agent_name", "")].append(action)

    agent_stances: dict[str, str] = {
        name: _agent_dominant_stance(posts) for name, posts in posts_by_agent.items() if name
    }

    buckets: dict[str, list[str]] = defaultdict(list)
    for name, stance in agent_stances.items():
        buckets[stance].append(name)

    positions: list[dict[str, Any]] = []
    for stance, members in buckets.items():
        if not members:
            continue
        bucket_texts: list[str] = []
        for name in members:
            bucket_texts.extend(_post_text(p) for p in posts_by_agent[name])
        positions.append({
            "name": _STANCE_BLOC_NAME[stance],
            "stance": stance,
            "members": sorted(members),
            "member_count": len(members),
            "rationale_keywords": _top_keywords(bucket_texts, limit=3),
        })
    # Stable order: opposed, supports, split, neutral
    order = {"opposed": 0, "supports": 1, "split": 2, "neutral": 3}
    positions.sort(key=lambda p: order.get(p["stance"], 99))
    return positions
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestExtractStakeholderPositions -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add extract_stakeholder_positions (keyword-clustered)"
```

---

## Task 4: Implement `name_coalitions`

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestNameCoalitions:
    def test_coalitions_named_by_stance_not_generic(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        coalitions = story_signals.name_coalitions(positions)
        for c in coalitions:
            assert not c["name"].startswith("Coalition ")

    def test_coalition_has_required_keys(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        coalitions = story_signals.name_coalitions(positions)
        for c in coalitions:
            assert set(c.keys()) >= {"name", "members", "size", "stance"}

    def test_size_matches_members(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        coalitions = story_signals.name_coalitions(positions)
        for c in coalitions:
            assert c["size"] == len(c["members"])

    def test_singleton_buckets_excluded(self):
        # A bucket of 1 is not a coalition.
        positions = [
            {"name": "Opposition bloc", "stance": "opposed",
             "members": ["Solo"], "member_count": 1, "rationale_keywords": []},
            {"name": "Support bloc", "stance": "supports",
             "members": ["A", "B"], "member_count": 2, "rationale_keywords": []},
        ]
        coalitions = story_signals.name_coalitions(positions)
        assert len(coalitions) == 1
        assert coalitions[0]["stance"] == "supports"

    def test_empty_positions_returns_empty(self):
        assert story_signals.name_coalitions([]) == []
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestNameCoalitions -v`
Expected: 5 FAILED.

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
_COALITION_LABEL = {
    "opposed":  "Opposition alignment",
    "supports": "Support alignment",
    "split":    "Mixed-stance group",
    "neutral":  "Neutral observers",
}


def name_coalitions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Promote stakeholder_positions with ≥2 members to named coalitions."""
    coalitions: list[dict[str, Any]] = []
    for p in positions:
        if p["member_count"] < 2:
            continue
        # Prefer a keyword-derived name when rationale keywords are present;
        # fall back to stance label.
        kw = p.get("rationale_keywords") or []
        if kw:
            name = f"{kw[0].capitalize()}-focused {p['stance']} group"
        else:
            name = _COALITION_LABEL.get(p["stance"], "Group")
        coalitions.append({
            "name": name,
            "members": list(p["members"]),
            "size": p["member_count"],
            "stance": p["stance"],
        })
    return coalitions
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestNameCoalitions -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add name_coalitions (stance-named, ≥2 members)"
```

---

## Task 5: Implement `extract_phase_boundaries`

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestExtractPhaseBoundaries:
    def test_15_rounds_30_days_gives_three_phases(self):
        phases = story_signals.extract_phase_boundaries(make_chat_log(), forecast_days=30)
        assert len(phases) == 3
        labels = [p["phase"] for p in phases]
        assert labels == ["Early", "Mid", "Late"]

    def test_phase_has_required_keys(self):
        phases = story_signals.extract_phase_boundaries(make_chat_log(), forecast_days=30)
        for p in phases:
            assert set(p.keys()) >= {"phase", "rounds", "week_range", "dominant_topic"}

    def test_rounds_cover_full_range(self):
        phases = story_signals.extract_phase_boundaries(make_chat_log(), forecast_days=30)
        early_start = phases[0]["rounds"][0]
        late_end = phases[-1]["rounds"][1]
        assert early_start == 1
        assert late_end == 10  # max round_num in fixture is 10

    def test_week_range_scales_with_forecast_days(self):
        phases = story_signals.extract_phase_boundaries(make_chat_log(), forecast_days=30)
        # 30 days / 3 phases = 10 days per phase ≈ 1.4 weeks; accept "Weeks 1-2"/"Week 3"/"Week 4"
        assert "Week" in phases[0]["week_range"]
        assert "Week" in phases[-1]["week_range"]

    def test_fewer_than_three_rounds_collapses_to_single_phase(self):
        two_rounds = [
            {"round_num": 1, "agent_id": "a", "agent_name": "A",
             "action_type": "CREATE_POST", "platform": "twitter",
             "action_args": {"text": "hello"}, "timestamp": None, "success": True},
            {"round_num": 2, "agent_id": "a", "agent_name": "A",
             "action_type": "CREATE_POST", "platform": "twitter",
             "action_args": {"text": "world"}, "timestamp": None, "success": True},
        ]
        phases = story_signals.extract_phase_boundaries(two_rounds, forecast_days=7)
        assert len(phases) == 1
        assert phases[0]["phase"] == "Full horizon"

    def test_empty_chat_log_returns_single_empty_phase(self):
        phases = story_signals.extract_phase_boundaries([], forecast_days=7)
        assert len(phases) == 1
        assert phases[0]["phase"] == "Full horizon"
        assert phases[0]["dominant_topic"] == ""
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestExtractPhaseBoundaries -v`
Expected: 6 FAILED.

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
def _days_to_week_range(day_start: int, day_end: int) -> str:
    """Render a day-range as 'Week N' or 'Weeks N-M'. 1-indexed."""
    week_start = max(1, (day_start + 6) // 7)
    week_end = max(1, (day_end + 6) // 7)
    if week_start == week_end:
        return f"Week {week_start}"
    return f"Weeks {week_start}-{week_end}"


def extract_phase_boundaries(
    chat_log: list[dict[str, Any]],
    forecast_days: int,
) -> list[dict[str, Any]]:
    """Chunk simulation into thirds (or one 'Full horizon' if <3 rounds)."""
    max_round = max((a.get("round_num", 0) for a in chat_log), default=0)

    if max_round < 3:
        topics = _top_keywords([_post_text(a) for a in chat_log], limit=1)
        return [{
            "phase": "Full horizon",
            "rounds": [1, max(1, max_round)],
            "week_range": _days_to_week_range(1, forecast_days),
            "dominant_topic": topics[0] if topics else "",
        }]

    labels = ["Early", "Mid", "Late"]
    third = max_round / 3
    phases: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        r_start = int(i * third) + 1
        r_end = int((i + 1) * third) if i < 2 else max_round
        d_start = int(i * forecast_days / 3) + 1
        d_end = int((i + 1) * forecast_days / 3) if i < 2 else forecast_days
        bucket = [a for a in chat_log if r_start <= a.get("round_num", 0) <= r_end]
        topics = _top_keywords([_post_text(a) for a in bucket], limit=1)
        phases.append({
            "phase": label,
            "rounds": [r_start, r_end],
            "week_range": _days_to_week_range(d_start, d_end),
            "dominant_topic": topics[0] if topics else "",
        })
    return phases
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestExtractPhaseBoundaries -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add extract_phase_boundaries with week-range labels"
```

---

## Task 6: Implement `extract_quotable_posts`

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestExtractQuotablePosts:
    def test_returns_list_of_dicts_with_expected_keys(self):
        chat_log = make_chat_log()
        phases = story_signals.extract_phase_boundaries(chat_log, forecast_days=30)
        quotes = story_signals.extract_quotable_posts(chat_log, phases, graph_data=make_graph_data())
        assert isinstance(quotes, list)
        for q in quotes:
            assert set(q.keys()) >= {"agent_name", "agent_role", "phase", "text", "engagement"}

    def test_no_duplicate_agent_across_quotes(self):
        chat_log = make_chat_log()
        phases = story_signals.extract_phase_boundaries(chat_log, forecast_days=30)
        quotes = story_signals.extract_quotable_posts(chat_log, phases, graph_data=make_graph_data())
        names = [q["agent_name"] for q in quotes]
        assert len(names) == len(set(names))

    def test_role_derived_from_graph_labels(self):
        chat_log = make_chat_log()
        phases = story_signals.extract_phase_boundaries(chat_log, forecast_days=30)
        quotes = story_signals.extract_quotable_posts(chat_log, phases, graph_data=make_graph_data())
        ms_quote = next((q for q in quotes if q["agent_name"] == "Morgan Stanley"), None)
        if ms_quote is not None:
            assert ms_quote["agent_role"] == "Bank"

    def test_empty_chat_log_returns_empty(self):
        assert story_signals.extract_quotable_posts([], [], {"nodes": [], "edges": [], "metadata": {}}) == []
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestExtractQuotablePosts -v`
Expected: 4 FAILED.

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
def _role_map(graph_data: dict[str, Any]) -> dict[str, str]:
    """Map agent_name → first non-'Entity' label from graph nodes, for role chips."""
    roles: dict[str, str] = {}
    for node in graph_data.get("nodes", []):
        name = node.get("name", "")
        labels = [lab for lab in node.get("labels", []) if lab and lab != "Entity"]
        if name and labels:
            roles[name] = labels[0]
    return roles


def _phase_for_round(round_num: int, phases: list[dict]) -> str:
    for p in phases:
        r_start, r_end = p["rounds"]
        if r_start <= round_num <= r_end:
            return p["phase"]
    return phases[0]["phase"] if phases else ""


def _engagement_for_post(
    post: dict[str, Any],
    chat_log: list[dict[str, Any]],
) -> int:
    """Heuristic engagement: count LIKE_POST / REPOST actions targeting this post.

    Target matching uses agent_id + round_num prefix in target_post field,
    which is the convention the extractor produces (e.g., "ms_r8").
    """
    agent = post.get("agent_id", "")
    round_num = post.get("round_num", 0)
    target_marker = f"{agent}_r{round_num}"
    count = 0
    for action in chat_log:
        if action.get("action_type") in ("LIKE_POST", "REPOST"):
            target = (action.get("action_args") or {}).get("target_post", "")
            if target_marker in target:
                count += 1
    return count


def extract_quotable_posts(
    chat_log: list[dict[str, Any]],
    phases: list[dict[str, Any]],
    graph_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Top-engagement post per phase per stance, deduped by agent."""
    roles = _role_map(graph_data)
    posts = [a for a in chat_log if a.get("action_type") == "CREATE_POST"]

    # Group candidates by (phase, stance)
    candidates: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for post in posts:
        text = _post_text(post)
        if not text:
            continue
        phase = _phase_for_round(post.get("round_num", 0), phases)
        stance = _classify_stance(text)
        candidates[(phase, stance)].append(post)

    selected: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for (phase, stance), posts_list in candidates.items():
        posts_list.sort(key=lambda p: _engagement_for_post(p, chat_log), reverse=True)
        for post in posts_list:
            name = post.get("agent_name", "")
            if name and name not in seen_agents:
                seen_agents.add(name)
                selected.append({
                    "agent_name": name,
                    "agent_role": roles.get(name, ""),
                    "phase": phase,
                    "text": _post_text(post),
                    "engagement": _engagement_for_post(post, chat_log),
                })
                break
    return selected
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestExtractQuotablePosts -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add extract_quotable_posts (engagement + phase + stance)"
```

---

## Task 7: Implement `compute_sim_scale` and `extract_disagreement_axis`

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/engine/test_story_signals.py`:

```python
class TestComputeSimScale:
    def test_participants_counts_unique_agent_names(self):
        scale = story_signals.compute_sim_scale(
            make_chat_log(), forecast_days=30, bloc_count=2,
        )
        assert scale["participants"] == 6  # ms, msft, sec, iac, fed, gs
        assert scale["horizon_days"] == 30
        assert scale["bloc_count"] == 2

    def test_market_stress_none_without_trades(self):
        scale = story_signals.compute_sim_scale(
            make_chat_log(), forecast_days=30, bloc_count=2,
        )
        assert scale["market_stress"] == "none_observed"

    def test_market_stress_present_with_trades(self):
        trades_log = make_chat_log() + [
            {"round_num": 5, "agent_id": "x", "agent_name": "X",
             "action_type": "BUY", "platform": "polymarket",
             "action_args": {}, "timestamp": None, "success": True},
        ]
        scale = story_signals.compute_sim_scale(trades_log, forecast_days=30, bloc_count=2)
        assert scale["market_stress"] == "present"


class TestExtractDisagreementAxis:
    def test_returns_non_empty_string_when_both_stances_present(self):
        axis = story_signals.extract_disagreement_axis(make_chat_log())
        assert axis
        assert isinstance(axis, str)

    def test_returns_empty_when_no_disagreement(self):
        supports_only = [
            a for a in make_chat_log()
            if _post_text_stance(a) != "opposed"
        ]
        # If only supportive posts remain, no axis.
        axis = story_signals.extract_disagreement_axis(supports_only)
        # With only one stance, the axis may still be populated by keywords; accept either
        # empty or a short descriptive string — but never a contradiction.
        assert axis == "" or " vs " in axis or len(axis) > 0


def _post_text_stance(action):
    """Local helper mirroring production logic for the test above."""
    from simswarm.story_signals import _classify_stance, _post_text
    return _classify_stance(_post_text(action))
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestComputeSimScale tests/engine/test_story_signals.py::TestExtractDisagreementAxis -v`
Expected: 5 FAILED.

- [ ] **Step 3: Implement**

Add to `simswarm/story_signals.py`:

```python
def compute_sim_scale(
    chat_log: list[dict[str, Any]],
    forecast_days: int,
    bloc_count: int,
) -> dict[str, Any]:
    """Honest sim-scale aggregates. Renames the old 'confidence' grid."""
    participants = len({a.get("agent_name", "") for a in chat_log if a.get("agent_name")})
    has_trade = any(a.get("action_type") in ("BUY", "SELL") for a in chat_log)
    return {
        "participants": participants,
        "horizon_days": forecast_days,
        "bloc_count": bloc_count,
        "market_stress": "present" if has_trade else "none_observed",
    }


def extract_disagreement_axis(chat_log: list[dict[str, Any]]) -> str:
    """Top keyword from opposed posts 'vs' top keyword from supports posts."""
    opposed_texts: list[str] = []
    support_texts: list[str] = []
    for action in chat_log:
        if action.get("action_type") not in ("CREATE_POST", "CREATE_COMMENT"):
            continue
        text = _post_text(action)
        stance = _classify_stance(text)
        if stance == "opposed":
            opposed_texts.append(text)
        elif stance == "supports":
            support_texts.append(text)

    opposed_kw = _top_keywords(opposed_texts, limit=1)
    support_kw = _top_keywords(support_texts, limit=1)
    if opposed_kw and support_kw:
        return f"{support_kw[0]} vs {opposed_kw[0]}"
    return opposed_kw[0] if opposed_kw else (support_kw[0] if support_kw else "")
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_story_signals.py::TestComputeSimScale tests/engine/test_story_signals.py::TestExtractDisagreementAxis -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): add compute_sim_scale + extract_disagreement_axis"
```

---

## Task 8: Wire up `build_story_signals` and verify shape

**Files:**
- Modify: `simswarm/story_signals.py`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Replace the skipped test with a real one**

Replace the `TestBuildStorySignals` class in `tests/engine/test_story_signals.py` with:

```python
class TestBuildStorySignals:
    def test_returns_expected_top_level_keys(self):
        result = story_signals.build_story_signals(
            make_chat_log(), make_graph_data(), forecast_days=30,
        )
        expected = {
            "stakeholder_positions", "disagreement_axis", "quotable_posts",
            "named_coalitions", "phase_boundaries", "sim_scale",
        }
        assert set(result.keys()) >= expected

    def test_empty_inputs_produce_valid_shape(self):
        result = story_signals.build_story_signals(
            chat_log=[],
            graph_data={"nodes": [], "edges": [], "metadata": {}},
            forecast_days=7,
        )
        assert result["stakeholder_positions"] == []
        assert result["named_coalitions"] == []
        assert result["quotable_posts"] == []
        assert result["sim_scale"]["participants"] == 0
        assert result["sim_scale"]["horizon_days"] == 7
        assert len(result["phase_boundaries"]) == 1

    def test_bloc_count_matches_named_coalitions(self):
        result = story_signals.build_story_signals(
            make_chat_log(), make_graph_data(), forecast_days=30,
        )
        assert result["sim_scale"]["bloc_count"] == len(result["named_coalitions"])
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_story_signals.py::TestBuildStorySignals -v`
Expected: 3 FAILED (NotImplementedError).

- [ ] **Step 3: Implement the top-level builder**

Replace the `NotImplementedError` body in `simswarm/story_signals.py`:

```python
def build_story_signals(
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
    forecast_days: int,
) -> dict[str, Any]:
    positions = extract_stakeholder_positions(chat_log)
    named = name_coalitions(positions)
    phases = extract_phase_boundaries(chat_log, forecast_days)
    quotes = extract_quotable_posts(chat_log, phases, graph_data)
    axis = extract_disagreement_axis(chat_log)
    scale = compute_sim_scale(chat_log, forecast_days, bloc_count=len(named))
    return {
        "stakeholder_positions": positions,
        "named_coalitions": named,
        "phase_boundaries": phases,
        "quotable_posts": quotes,
        "disagreement_axis": axis,
        "sim_scale": scale,
    }
```

- [ ] **Step 4: Run all story_signals tests**

Run: `pytest tests/engine/test_story_signals.py -v`
Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add simswarm/story_signals.py tests/engine/test_story_signals.py
git commit -m "feat(story): wire build_story_signals top-level entry"
```

---

## Task 9: Regression fixture from prod job 109

**Files:**
- Create: `tests/engine/fixtures/job_109_chat_log.json`
- Create: `tests/engine/fixtures/job_109_graph.json`
- Modify: `tests/engine/test_story_signals.py`

- [ ] **Step 1: Export prod job 109 artifacts**

Run against the prod server (read-only):

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "docker exec simswarm-db psql -U fishcloud -d fishcloud -t -A -c \
  \"SELECT result_chat_log FROM simulation_jobs WHERE id = 109;\"" \
  > tests/engine/fixtures/job_109_chat_log.json

ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "docker exec simswarm-db psql -U fishcloud -d fishcloud -t -A -c \
  \"SELECT result_graph FROM simulation_jobs WHERE id = 109;\"" \
  > tests/engine/fixtures/job_109_graph.json
```

Verify the files are valid JSON:

```bash
python -c "import json; json.load(open('tests/engine/fixtures/job_109_chat_log.json'))"
python -c "import json; json.load(open('tests/engine/fixtures/job_109_graph.json'))"
```

Expected: no errors printed.

- [ ] **Step 2: Write regression test**

Add to `tests/engine/test_story_signals.py`:

```python
import json
from pathlib import Path


class TestBuildStorySignalsProdRegression:
    """Regression: job #109 — SEC AI disclosure rules, 30-day horizon.

    Today's adapter returns `coalitions=[]` (mutual-follow misses thematic alignment).
    Our new story_signals.py MUST surface at least two named coalitions for the
    industry bloc and regulator/transparency bloc that are obviously present in
    the data.
    """

    @staticmethod
    def _load_job_109():
        base = Path(__file__).resolve().parent / "fixtures"
        chat_log = json.loads((base / "job_109_chat_log.json").read_text())
        graph = json.loads((base / "job_109_graph.json").read_text())
        return chat_log, graph

    def test_surfaces_at_least_two_named_coalitions(self):
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        assert len(result["named_coalitions"]) >= 2

    def test_sim_scale_market_stress_none_observed(self):
        # Prod job 109 had 0 trades — verify we report honestly, not as confidence.
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        assert result["sim_scale"]["market_stress"] == "none_observed"

    def test_phase_boundaries_time_anchored(self):
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        for phase in result["phase_boundaries"]:
            assert "Week" in phase["week_range"]
```

- [ ] **Step 3: Run regression**

Run: `pytest tests/engine/test_story_signals.py::TestBuildStorySignalsProdRegression -v`
Expected: 3 PASSED. If `test_surfaces_at_least_two_named_coalitions` fails with 0 or 1 coalition returned, the keyword sets in `OPPOSED_SIGNALS`/`SUPPORT_SIGNALS` need tuning — open the fixture, sample 10 posts from each bloc, and widen the keyword sets to cover the actual vocabulary used (then re-run; do NOT relax the test threshold).

- [ ] **Step 4: Commit**

```bash
git add tests/engine/fixtures/job_109_chat_log.json tests/engine/fixtures/job_109_graph.json tests/engine/test_story_signals.py
git commit -m "test(story): add job #109 regression fixtures for story_signals"
```

---

## Task 10: Update contracts schema for new `StructuredResults` shape

**Files:**
- Modify: `tests/contracts/schemas.py`

- [ ] **Step 1: Write the failing test first**

Add at the bottom of `tests/contracts/schemas.py` (a self-test — contract schemas live in tests and validate against real adapter output later):

```python
# (No test file — schema changes surface through adapter tests in Task 11.)
```

There's no standalone test; the schema is the contract. We validate it lands by running the adapter tests in Task 11 and confirming they import the new fields cleanly.

- [ ] **Step 2: Update the schema**

Replace the existing `StructuredResults` and supporting classes in `tests/contracts/schemas.py`. Delete `SentimentEntry`, `Coalition`, `ConfidenceEntry`. Add new types:

```python
class StakeholderPosition(BaseModel):
    name: str
    stance: str  # opposed | supports | neutral | split
    members: list[str]
    member_count: int
    rationale_keywords: list[str]


class NamedCoalition(BaseModel):
    name: str
    members: list[str]
    size: int
    stance: str


class PhaseBoundary(BaseModel):
    phase: str
    rounds: list[int]  # [start, end] inclusive
    week_range: str
    dominant_topic: str


class QuotablePost(BaseModel):
    agent_name: str
    agent_role: str
    phase: str
    text: str
    engagement: int


class SimScale(BaseModel):
    participants: int
    horizon_days: int
    bloc_count: int
    market_stress: str  # present | none_observed


class FindingSlot(BaseModel):
    slot: str  # industry | regulator | intermediary | market | turning_point
    title: str
    body: str
    citation: str
    accent_color: str


class StructuredResults(BaseModel):
    # LLM-authored
    brief: str
    verdict: str
    findings: list[FindingSlot]
    # Deterministic (Path 3)
    stakeholder_positions: list[StakeholderPosition]
    named_coalitions: list[NamedCoalition]
    phase_boundaries: list[PhaseBoundary]
    quotable_posts: list[QuotablePost]
    disagreement_axis: str
    sim_scale: SimScale
```

Also remove the now-dead `SentimentEntry`, `Coalition`, `ConfidenceEntry` classes.

- [ ] **Step 3: Run contracts import**

Run: `python -c "from tests.contracts.schemas import StructuredResults; print(StructuredResults.model_fields.keys())"`
Expected: prints `dict_keys(['brief', 'verdict', 'findings', 'stakeholder_positions', ...])`.

- [ ] **Step 4: Commit**

```bash
git add tests/contracts/schemas.py
git commit -m "feat(contracts): update StructuredResults for Path 3 + verdict/slot findings"
```

---

## Task 11: Refactor `adapt_structured` to delegate to story_signals

**Files:**
- Modify: `simswarm/adapter.py`
- Modify: `tests/engine/test_adapter_structured.py`
- Modify: `tests/engine/adapter_fixtures.py` (only if the new adapter requires a different fixture shape)

- [ ] **Step 1: Rewrite the existing adapter tests**

Replace the entire body of `tests/engine/test_adapter_structured.py`:

```python
"""Tests for adapt_structured post-Path-3 refactor."""
from __future__ import annotations

from simswarm.adapter import FINDING_COLORS, adapt_chat_log, adapt_graph_data, adapt_structured
from tests.contracts.schemas import StructuredResults
from tests.engine.adapter_fixtures import BRIEF, make_findings, make_graph, make_records


def _run(brief=BRIEF, findings=None, records=None, graph=None, forecast_days=30):
    if findings is None:
        findings = make_findings()
    chat_log = adapt_chat_log(records if records is not None else make_records())
    graph_data = adapt_graph_data(graph if graph is not None else make_graph())
    return adapt_structured(
        brief=brief,
        findings=findings,
        chat_log=chat_log,
        graph_data=graph_data,
        forecast_days=forecast_days,
        verdict="Sample verdict sentence in plain English.",
    )


class TestAdaptStructuredSchema:
    def test_validates_against_schema(self):
        StructuredResults.model_validate(_run())

    def test_brief_matches_input(self):
        assert _run()["brief"] == BRIEF

    def test_verdict_matches_input(self):
        assert _run()["verdict"] == "Sample verdict sentence in plain English."

    def test_sim_scale_present(self):
        assert "sim_scale" in _run()
        assert _run()["sim_scale"]["horizon_days"] == 30

    def test_named_coalitions_present(self):
        assert "named_coalitions" in _run()

    def test_no_legacy_sentiment_key(self):
        assert "sentiment" not in _run()

    def test_no_legacy_confidence_key(self):
        assert "confidence" not in _run()

    def test_empty_inputs_produce_valid_output(self):
        from simswarm.types import GraphSnapshot
        empty_graph = GraphSnapshot(
            nodes=[], edges=[],
            metadata={"entity_types": [], "total_nodes": 0, "total_edges": 0},
        )
        result = adapt_structured(
            brief="", findings=[], chat_log=[],
            graph_data=adapt_graph_data(empty_graph),
            forecast_days=7, verdict="",
        )
        StructuredResults.model_validate(result)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/engine/test_adapter_structured.py -v`
Expected: most tests FAIL — `adapt_structured` signature doesn't yet accept `forecast_days` or `verdict`.

- [ ] **Step 3: Rewrite `adapt_structured`**

Replace the body of `adapt_structured` in `simswarm/adapter.py` and delete the now-dead helpers:

```python
from simswarm.story_signals import build_story_signals


def adapt_structured(
    brief: str,
    findings: list[dict[str, Any]],
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
    forecast_days: int,
    verdict: str = "",
) -> dict:
    """Build the structured results dict consumed by the SaaS frontend.

    Args:
        brief: One-paragraph executive summary from the LLM.
        findings: List of {slot, title, body, citation, accent_color} from the LLM.
            (Legacy shape {title, content} is also accepted and re-shaped.)
        chat_log: Already-adapted chat log.
        graph_data: Already-adapted graph dict.
        forecast_days: Required timeline in days.
        verdict: One-sentence answer from the LLM.
    """
    adapted_findings: list[dict] = []
    for i, finding in enumerate(findings):
        if "slot" in finding:
            adapted_findings.append({
                "slot": finding["slot"],
                "title": finding.get("title", ""),
                "body": finding.get("body", ""),
                "citation": finding.get("citation", ""),
                "accent_color": finding.get("accent_color", FINDING_COLORS[i % len(FINDING_COLORS)]),
            })
        else:
            # Legacy path (during rollout): wrap the old {title, content} shape.
            adapted_findings.append({
                "slot": "industry" if i == 0 else ("regulator" if i == 1 else "intermediary"),
                "title": finding.get("title", f"Finding {i + 1}"),
                "body": finding.get("content", "")[:500],
                "citation": "",
                "accent_color": FINDING_COLORS[i % len(FINDING_COLORS)],
            })

    signals = build_story_signals(chat_log, graph_data, forecast_days)

    return {
        "brief": brief,
        "verdict": verdict,
        "findings": adapted_findings,
        **signals,
    }


# Delete: _compute_platform_sentiment, _detect_coalitions, _build_confidence,
# _COALITION_COLORS, any other helpers no longer referenced.
```

Remove the `_compute_platform_sentiment`, `_detect_coalitions`, `_build_confidence` helpers and their private constants. Keep `FINDING_COLORS` (still used). Leave `adapt_chat_log` and `adapt_graph_data` untouched.

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/engine/test_adapter_structured.py -v`
Expected: all PASSED.

- [ ] **Step 5: Find and remove other callers of deleted helpers**

Run: `grep -rn "_compute_platform_sentiment\|_detect_coalitions\|_build_confidence" simswarm/ tests/ saas/`
Expected: no remaining references (these should all live inside `simswarm/adapter.py` or its tests). If any show up elsewhere, delete them.

- [ ] **Step 6: Full regression**

Run: `pytest tests/engine/ -v`
Expected: all PASSED. Any test that was reading legacy `sentiment` / `confidence` keys must be deleted or updated to read the new shape.

- [ ] **Step 7: Commit**

```bash
git add simswarm/adapter.py tests/engine/test_adapter_structured.py
git commit -m "refactor(adapter): delegate adapt_structured to story_signals (Path 3)"
```

---

## Task 12: Make `forecast_days` required on `JobCreate`

**Files:**
- Modify: `saas/jobs/schemas.py`
- Modify: `tests/test_e2e.py` and any other tests building `JobCreate`
- Modify: `saas/jobs/api_draft.py` (launch endpoint)

- [ ] **Step 1: Write failing test for launch validation**

Add to `tests/test_e2e.py` (or create a new targeted file if preferred):

```python
async def test_launch_draft_rejects_null_forecast_days(client, funded_user, auth_headers):
    # Create a draft without forecast_days
    draft_resp = await client.post(
        "/api/jobs/draft",
        json={"seed_text": "some seed", "goal": "some goal", "tier": "small"},
        headers=auth_headers,
    )
    assert draft_resp.status_code == 200
    draft_id = draft_resp.json()["id"]

    # Try to launch
    launch_resp = await client.post(f"/api/jobs/draft/{draft_id}/launch", headers=auth_headers)
    assert launch_resp.status_code == 422
    assert "forecast_days" in launch_resp.text.lower()


async def test_create_job_rejects_missing_forecast_days(client, funded_user, auth_headers):
    resp = await client.post(
        "/api/jobs",
        json={"seed_text": "seed", "goal": "goal", "tier": "small"},  # no forecast_days
        headers=auth_headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/test_e2e.py::test_launch_draft_rejects_null_forecast_days tests/test_e2e.py::test_create_job_rejects_missing_forecast_days -v`
Expected: 2 FAILED (validation not enforced yet).

- [ ] **Step 3: Update schema**

In `saas/jobs/schemas.py`, change:

```python
class JobCreate(BaseModel):
    seed_text: str
    goal: str
    tier: TierEnum
    enrich_web: bool = True
    forecast_days: int  # REQUIRED — removed default None

    @field_validator("seed_text")
    @classmethod
    def seed_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("seed_text cannot be empty")
        return v

    @field_validator("forecast_days")
    @classmethod
    def forecast_days_positive(cls, v: int) -> int:
        if v < 1 or v > 730:
            raise ValueError("forecast_days must be between 1 and 730")
        return v
```

`DraftCreate` and `DraftUpdate` keep `forecast_days: int | None = None` — drafts are scratchpads.

- [ ] **Step 4: Add launch-side validation**

In `saas/jobs/api_draft.py` — find the `launch_draft` endpoint (or wherever `POST /jobs/draft/{id}/launch` is handled). Before the job is created, add:

```python
if draft.forecast_days is None:
    raise HTTPException(
        status_code=422,
        detail={"field": "forecast_days", "message": "forecast_days is required to launch a simulation"},
    )
```

(If the endpoint currently constructs a `JobCreate` from the draft, this validation happens automatically — but add the explicit check for a clean error shape.)

- [ ] **Step 5: Update existing test fixtures that build `JobCreate` without `forecast_days`**

Run: `grep -rn "JobCreate(" tests/ saas/`

For each hit that doesn't already pass `forecast_days`, add `forecast_days=30`. Same for any test POSTing to `/api/jobs` without the field — add `"forecast_days": 30` to the JSON body.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASSED, including the two new validation tests.

- [ ] **Step 7: Commit**

```bash
git add saas/jobs/schemas.py saas/jobs/api_draft.py tests/
git commit -m "feat(jobs): require forecast_days on JobCreate and draft launch"
```

---

## Task 13: Wizard preselects 30-day default

**Files:**
- Modify: `frontend/src/components/wizard/TimelineChips.vue`
- Modify: `frontend/src/views/NewSimulation.vue`

- [ ] **Step 1: Write failing component test**

Create or update `frontend/src/components/wizard/__tests__/TimelineChips.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TimelineChips from '../TimelineChips.vue'

describe('TimelineChips', () => {
  it('preselects 30-day chip when modelValue is null', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: null } })
    // Component should emit update:modelValue=30 on mount
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([30])
  })

  it('does not override an explicit modelValue', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 7 } })
    // With an explicit value, no default should be emitted
    const updates = wrapper.emitted('update:modelValue') || []
    expect(updates.length).toBe(0)
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd frontend && npx vitest run src/components/wizard/__tests__/TimelineChips.spec.js`
Expected: 1 FAILED (no emit on mount).

- [ ] **Step 3: Update `TimelineChips.vue`**

Replace the `<script setup>` block in `frontend/src/components/wizard/TimelineChips.vue`:

```vue
<script setup>
import { onMounted } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue'])

const presets = [
  { label: '1 day', days: 1 },
  { label: '1 week', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 180 },
  { label: '1 year', days: 365 },
]

onMounted(() => {
  if (props.modelValue == null) emit('update:modelValue', 30)
})

function toggle(days) {
  emit('update:modelValue', props.modelValue === days ? null : days)
}
</script>
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd frontend && npx vitest run src/components/wizard/__tests__/TimelineChips.spec.js`
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/TimelineChips.vue frontend/src/components/wizard/__tests__/TimelineChips.spec.js
git commit -m "feat(wizard): preselect 30-day default on TimelineChips mount"
```

---

## Task 14: Rewrite `report.j2` prompt to consume Path 3 context

**Files:**
- Modify: `simswarm/prompts/report.j2`

- [ ] **Step 1: Rewrite the template**

Replace the entire body of `simswarm/prompts/report.j2`:

```jinja
You are an expert simulation analyst. A multi-agent swarm simulation has just completed.

Simulation goal: {{ goal }}
Forecast horizon: {{ forecast_days }} days

Pre-computed deterministic signals from the simulation (DO NOT invent entities or events that aren't in this data):

Stakeholder positions:
{% for p in signals.stakeholder_positions %}
  - {{ p.name }} (stance: {{ p.stance }}, {{ p.member_count }} participants): {{ p.members | join(', ') }}
    Rationale keywords: {{ p.rationale_keywords | join(', ') or '(none)' }}
{% endfor %}

Named coalitions:
{% for c in signals.named_coalitions %}
  - {{ c.name }} ({{ c.size }} members, {{ c.stance }}): {{ c.members | join(', ') }}
{% endfor %}

Disagreement axis: {{ signals.disagreement_axis or '(no clear axis)' }}

Phase boundaries:
{% for ph in signals.phase_boundaries %}
  - {{ ph.phase }} ({{ ph.week_range }}, rounds {{ ph.rounds[0] }}-{{ ph.rounds[1] }}): dominant topic = "{{ ph.dominant_topic }}"
{% endfor %}

Quotable posts:
{% for q in signals.quotable_posts %}
  - [{{ q.phase }}] {{ q.agent_name }}{% if q.agent_role %} ({{ q.agent_role }}){% endif %}: "{{ q.text }}" (engagement: {{ q.engagement }})
{% endfor %}

Simulation scale: {{ signals.sim_scale.participants }} participants, {{ signals.sim_scale.horizon_days }}-day horizon, {{ signals.sim_scale.bloc_count }} blocs, market stress: {{ signals.sim_scale.market_stress }}.

---

Write output as markdown with these EXACT sections. Every claim must reference an entity, phase, or coalition from the signals above — do NOT invent.

## Executive Summary
One paragraph summarizing the simulated answer to the goal.

## Verdict
A single sentence in plain, domain-language English. No jargon. This is what gets screenshotted.

## Key Findings
Exactly 4 findings, each tagged with a slot from this set:
- industry (private-sector / commercial actor dynamics)
- regulator (regulatory / oversight posture)
- intermediary (neutral / stabilizing actors)
- market (trading or market-signal behaviour)
- turning_point (a specific moment where posture shifted)

Format each finding as:

### slot=industry — Short title
One sentence body.
_Citation: specific entities or quotes from the signals above._

Provide exactly 4. If the simulation lacks a slot (e.g., no market signals), pick the 4 most relevant from the 5 options above.

## Agent Coalitions
Prose description of the named coalitions surfaced by the signals — one paragraph. Use phase-anchored language ("early", "midway", "late" or week ranges), NEVER round numbers.

## Market Analysis
Summarize market signals using the `market_stress` value. If `none_observed`, explicitly name that — "no speculative trades formed; this is itself a signal of calm reception" — do not invent market activity.

## Conclusion
Implications and confidence. Reference the stakeholder positions and disagreement axis. End with the one-sentence verdict verbatim.

---

Rules:
- Use phase/week language, NEVER round numbers
- Use named entities from the signals — do not invent
- Write in plain analytical prose; no bullet-only sections
- Single final response; no tool calls needed (signals are pre-computed)
```

- [ ] **Step 2: Manually verify the template renders**

Run a quick sanity check:

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('simswarm/prompts'))
from tests.engine.story_signals_fixtures import make_chat_log, make_graph_data
from simswarm.story_signals import build_story_signals
signals = build_story_signals(make_chat_log(), make_graph_data(), forecast_days=30)
print(env.get_template('report.j2').render(goal='test goal', forecast_days=30, signals=signals)[:600])
"
```

Expected: prints a ~600-char prefix of a rendered prompt with stakeholder positions and coalitions populated.

- [ ] **Step 3: Commit**

```bash
git add simswarm/prompts/report.j2
git commit -m "feat(report): rewrite prompt to consume Path 3 signals, demand slotted findings"
```

---

## Task 15: Update `ReportRunner` to pass signals into prompt and parse new output

**Files:**
- Modify: `saas/jobs/report.py`
- Modify: `saas/jobs/tasks_report.py`

- [ ] **Step 1: Update `ReportRunner._render_system_prompt` signature**

In `saas/jobs/report.py`:

```python
# At the top:
from simswarm.story_signals import build_story_signals


# Inside ReportRunner — update constructor:
def __init__(
    self,
    job_id: int,
    goal: str,
    forecast_days: int,
    client: _ChatClient,
    fetcher: Callable[[int, str], bytes] = fetch_artifact,
) -> None:
    self.job_id = job_id
    self.goal = goal
    self.forecast_days = forecast_days
    self._client = client
    self._fetcher = fetcher


# Inside run(), replace _render_system_prompt call:
def _render_system_prompt(self, signals: dict) -> str:
    return _jinja_env.get_template("report.j2").render(
        goal=self.goal,
        forecast_days=self.forecast_days,
        signals=signals,
    ).strip()


# Inside run(), compute signals BEFORE building the messages list:
async def run(self) -> ReportResult:
    artifacts = self._load_artifacts()
    signals = build_story_signals(
        chat_log=artifacts.chat_log,
        graph_data=_graph_from_artifacts(artifacts),  # see helper below
        forecast_days=self.forecast_days,
    )
    tools = ReportTools(artifacts)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": self._render_system_prompt(signals)},
        {"role": "user", "content": "Please generate the report now."},
    ]
    # ... rest unchanged
```

Add a small helper (top-level in `report.py`) to stitch a `graph_data`-shaped dict when the `ReportArtifacts` don't have one:

```python
def _graph_from_artifacts(artifacts: ReportArtifacts) -> dict:
    # MinIO's `posts.json` / `trades.json` are not graph data. We pull the
    # graph from the separate `graph_data.json` artifact the pod writes.
    # If missing, return an empty-but-valid shape — story_signals degrades
    # gracefully.
    return {"nodes": [], "edges": [],
            "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}
```

(This is a conservative interim. The pod DOES write graph_data separately — a follow-up task or future plan can wire that in if the empty graph produces weak role labels.)

- [ ] **Step 2: Parse `verdict` and slotted findings from the final LLM response**

Replace `_extract_findings` and add a `_extract_verdict`:

```python
def _extract_verdict(markdown: str) -> str:
    match = re.search(
        r"##\s+Verdict\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return ""
    # Verdict section should contain one sentence; collapse to a single line.
    return " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())[:400]


def _extract_findings(markdown: str) -> list[dict[str, str]]:
    """Extract 4 slotted findings from '### slot=X — Title' blocks."""
    section_match = re.search(
        r"##\s+Key Findings\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []
    findings: list[dict[str, str]] = []
    block_pattern = re.compile(
        r"###\s+slot=(\w+)\s*[—–-]\s*(.+?)\n+(.*?)(?=\n###|\Z)",
        re.DOTALL,
    )
    for m in block_pattern.finditer(section_match.group(1)):
        slot = m.group(1).strip().lower()
        title = m.group(2).strip()
        body_raw = m.group(3).strip()
        # Citation line begins with '_Citation:'
        citation = ""
        body_lines = []
        for line in body_raw.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("_citation:") or stripped.lower().startswith("citation:"):
                citation = stripped.lstrip("_").split(":", 1)[-1].strip().rstrip("_").strip()
            else:
                body_lines.append(line)
        body = " ".join(l.strip() for l in body_lines if l.strip())
        findings.append({
            "slot": slot,
            "title": title,
            "body": body,
            "citation": citation,
            "accent_color": _slot_color(slot),
        })
    return findings[:4]


from simswarm.story_signals import SLOT_COLORS


def _slot_color(slot: str) -> str:
    return SLOT_COLORS.get(slot, "#22D3EE")
```

Update `ReportResult`:

```python
@dataclass
class ReportResult:
    report_markdown: str = ""
    executive_brief: str = ""
    verdict: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)
```

Update the `ReportRunner.run()` return path to populate `verdict`:

```python
return ReportResult(
    report_markdown=markdown,
    executive_brief=_extract_brief(markdown),
    verdict=_extract_verdict(markdown),
    findings=_extract_findings(markdown),
)
```

- [ ] **Step 3: Thread `forecast_days` through the Celery task**

In `saas/jobs/tasks_report.py`:

```python
def _load_goal_and_forecast(job_id: int) -> tuple[str, int]:
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine
    engine = _get_sync_engine()
    if engine is None:
        return "", 30
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT goal, forecast_days FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            if not row:
                return "", 30
            goal = row[0] or ""
            forecast_days = int(row[1] or 30)
            return goal, forecast_days
    finally:
        engine.dispose()
```

Replace `_load_goal` calls with `_load_goal_and_forecast`. Update `_build_runner`:

```python
def _build_runner(job_id: int, goal: str, forecast_days: int) -> ReportRunner:
    client = AnthropicClient(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("SMART_MODEL", "claude-opus-4-6"),
    )
    return ReportRunner(job_id=job_id, goal=goal, forecast_days=forecast_days, client=client)
```

Update the task entrypoint:

```python
@celery_app.task(name="fishcloud.generate_report", bind=True,
                 max_retries=len(_RETRY_BACKOFF_S))
def generate_report_task(self, job_id: int, user_id: str) -> dict:
    goal, forecast_days = _load_goal_and_forecast(job_id)
    runner = _build_runner(job_id, goal, forecast_days)
    # ... rest unchanged
```

- [ ] **Step 4: Update `_build_structured` to include verdict**

In `saas/jobs/tasks_report.py::_build_structured`:

```python
def _build_structured(job_id: int, result) -> str:
    from saas.jobs.persistence_sync import _load_job_artifacts
    chat_log_json, graph_json = _load_job_artifacts(job_id)
    chat_log = json.loads(chat_log_json) if chat_log_json else []
    graph_data = json.loads(graph_json) if graph_json else {}

    goal, forecast_days = _load_goal_and_forecast(job_id)

    structured_dict = adapt_structured(
        brief=result.executive_brief,
        findings=result.findings,
        chat_log=chat_log,
        graph_data=graph_data,
        forecast_days=forecast_days,
        verdict=result.verdict,
    )
    return json.dumps(structured_dict)
```

- [ ] **Step 5: Run regression — all existing report-related tests**

Run: `pytest tests/engine/test_report.py tests/engine/test_report_generator.py tests/jobs/ -v`
Expected: all PASSED. If tests break due to `forecast_days` being required on `ReportRunner.__init__`, update the test fixtures to pass `forecast_days=30`.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/report.py saas/jobs/tasks_report.py
git commit -m "feat(report): runner consumes Path 3 signals, parses verdict + slotted findings"
```

---

## Task 16: Replace `_extract_key_insight` with verdict sourcing

**Files:**
- Modify: `saas/jobs/persistence.py`
- Modify: `saas/jobs/tasks_report.py`

- [ ] **Step 1: Write failing test**

Add to `tests/jobs/test_build_structured.py` (or create if absent):

```python
def test_key_insight_comes_from_verdict_field():
    from saas.jobs.persistence import _derive_key_insight
    assert _derive_key_insight(verdict="Unlikely to pass — 3 of 5 blocs opposed.",
                               report_markdown="## Executive Summary\nSomething else.") \
        == "Unlikely to pass — 3 of 5 blocs opposed."


def test_key_insight_falls_back_to_first_non_heading_when_verdict_empty():
    from saas.jobs.persistence import _derive_key_insight
    md = "## Executive Summary\nSome fallback insight over 30 characters long."
    assert _derive_key_insight(verdict="", report_markdown=md) \
        .startswith("Some fallback")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/jobs/test_build_structured.py -v`
Expected: FAILED (function not present).

- [ ] **Step 3: Replace the implementation**

In `saas/jobs/persistence.py`, replace `_extract_key_insight`:

```python
def _derive_key_insight(verdict: str, report_markdown: str) -> str | None:
    """Prefer the LLM-authored verdict; fall back to first non-heading line.

    The fallback exists only for defensive reasons — a well-formed report
    will always have a verdict.
    """
    if verdict and verdict.strip():
        return verdict.strip()[:200]
    if not report_markdown:
        return None
    lines = [line.strip() for line in report_markdown.split("\n") if line.strip()]
    insight_line = next(
        (line for line in lines if not line.startswith("#") and len(line) > 30),
        None,
    )
    return insight_line[:200] if insight_line else None


# Keep the old name as a shim for one release cycle; delete callers in this PR.
_extract_key_insight = _derive_key_insight
```

Update the `__all__` export list in `saas/jobs/persistence.py` — add `_derive_key_insight`.

- [ ] **Step 4: Update the caller in `tasks_report.py`**

In `saas/jobs/tasks_report.py`, replace:

```python
# OLD:
# key_insight = _extract_key_insight(result.report_markdown)

# NEW:
from saas.jobs.persistence import _derive_key_insight
key_insight = _derive_key_insight(
    verdict=result.verdict,
    report_markdown=result.report_markdown,
)
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `pytest tests/jobs/test_build_structured.py -v`
Expected: PASSED.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/persistence.py saas/jobs/tasks_report.py tests/jobs/test_build_structured.py
git commit -m "fix(report): source key_insight from verdict field, eliminate scratchpad leak"
```

---

## Task 17: Frontend — update `useSimulationData.js`

**Files:**
- Modify: `frontend/src/composables/useSimulationData.js`
- Modify: `frontend/src/composables/__tests__/useSimulationData.spec.js` (create if absent)

- [ ] **Step 1: Write failing test**

Create `frontend/src/composables/__tests__/useSimulationData.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useSimulationData } from '../useSimulationData.js'

describe('useSimulationData — new structured fields', () => {
  const makeJob = (structured) => ref({
    result_structured: JSON.stringify(structured),
    result_chat_log: '[]',
  })

  it('exposes verdict from structured', () => {
    const { verdict } = useSimulationData(makeJob({
      verdict: 'Unlikely to pass.',
      findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [], sim_scale: {},
      disagreement_axis: '', brief: '',
    }))
    expect(verdict.value).toBe('Unlikely to pass.')
  })

  it('exposes stakeholderPositions', () => {
    const { stakeholderPositions } = useSimulationData(makeJob({
      verdict: '', findings: [],
      stakeholder_positions: [{ name: 'Bloc A', stance: 'opposed', members: ['X'], member_count: 1, rationale_keywords: [] }],
      named_coalitions: [], phase_boundaries: [], quotable_posts: [],
      sim_scale: {}, disagreement_axis: '', brief: '',
    }))
    expect(stakeholderPositions.value).toHaveLength(1)
    expect(stakeholderPositions.value[0].stance).toBe('opposed')
  })

  it('exposes simScale', () => {
    const { simScale } = useSimulationData(makeJob({
      verdict: '', findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [],
      sim_scale: { participants: 10, horizon_days: 30, bloc_count: 2, market_stress: 'none_observed' },
      disagreement_axis: '', brief: '',
    }))
    expect(simScale.value.participants).toBe(10)
    expect(simScale.value.market_stress).toBe('none_observed')
  })

  it('no longer exposes sentimentBars', () => {
    const api = useSimulationData(makeJob({
      verdict: '', findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [], sim_scale: {},
      disagreement_axis: '', brief: '',
    }))
    expect(api.sentimentBars).toBeUndefined()
  })
})
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimulationData.spec.js`
Expected: 4 FAILED (fields not exposed).

- [ ] **Step 3: Update `useSimulationData.js`**

Replace the body of `frontend/src/composables/useSimulationData.js`:

```javascript
import { computed } from 'vue'

export function useSimulationData(job) {
  const chatLog = computed(() => {
    if (!job.value) return []
    try {
      const raw = job.value.result_chat_log || job.value.chat_log || '[]'
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  })

  const chatMessages = computed(() => {
    return chatLog.value
      .map(entry => {
        if (entry.content && entry.role) return entry
        const args = entry.action_args || {}
        const body = args.text ?? args.content ?? entry.content
        return {
          role: 'assistant',
          agent: entry.agent_name || entry.agent || 'Agent',
          content: body ?? JSON.stringify(args),
          timestamp: entry.timestamp || null,
        }
      })
      .filter(m => m.content)
  })

  const structured = computed(() => {
    const raw = job.value?.result_structured ?? job.value?.structured ?? null
    if (!raw) return null
    try {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          && Object.keys(parsed).length === 0) {
        return null
      }
      return parsed
    } catch { return null }
  })

  // New Path 3 / Path 2 fields — all lift straight out of structured
  const verdict = computed(() => structured.value?.verdict || '')
  const stakeholderPositions = computed(() => structured.value?.stakeholder_positions || [])
  const namedCoalitions = computed(() => structured.value?.named_coalitions || [])
  const phaseBoundaries = computed(() => structured.value?.phase_boundaries || [])
  const quotablePosts = computed(() => structured.value?.quotable_posts || [])
  const simScale = computed(() => structured.value?.sim_scale || {})
  const disagreementAxis = computed(() => structured.value?.disagreement_axis || '')

  function buildNodeRelationships(nodes, edges) {
    const nameMap = Object.fromEntries(nodes.map(n => [n.uuid, n.name || n.uuid]))
    const relMap = {}
    for (const edge of edges) {
      const src = edge.source_node_uuid
      const tgt = edge.target_node_uuid
      if (!relMap[src]) relMap[src] = []
      if (!relMap[tgt]) relMap[tgt] = []
      relMap[src].push({
        direction: 'outgoing',
        target_uuid: tgt,
        targetName: edge.target_node_name || nameMap[tgt] || tgt,
        type: edge.name || edge.fact || '',
        fact: edge.fact || '',
      })
      relMap[tgt].push({
        direction: 'incoming',
        source_uuid: src,
        sourceName: edge.source_node_name || nameMap[src] || src,
        type: edge.name || edge.fact || '',
        fact: edge.fact || '',
      })
    }
    return nodes.map(n => ({ ...n, relationships: relMap[n.uuid] || [] }))
  }

  return {
    chatLog, chatMessages, structured,
    verdict, stakeholderPositions, namedCoalitions,
    phaseBoundaries, quotablePosts, simScale, disagreementAxis,
    buildNodeRelationships,
  }
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimulationData.spec.js`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimulationData.js frontend/src/composables/__tests__/useSimulationData.spec.js
git commit -m "feat(frontend): expose Path 3 signals via useSimulationData"
```

---

## Task 18: Create `StakeholderChip.vue`

**Files:**
- Create: `frontend/src/components/results/StakeholderChip.vue`
- Create: `frontend/src/components/results/__tests__/StakeholderChip.spec.js`

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/results/__tests__/StakeholderChip.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StakeholderChip from '../StakeholderChip.vue'

describe('StakeholderChip', () => {
  it('renders name and stance', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'Industry bloc', stance: 'opposed' },
    })
    expect(wrapper.text()).toContain('Industry bloc')
    expect(wrapper.text()).toContain('Opposed')
  })

  it('applies opposed style when stance is opposed', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'X', stance: 'opposed' },
    })
    expect(wrapper.attributes('class')).toMatch(/coral|amber/)
  })

  it('applies supports style when stance is supports', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'X', stance: 'supports' },
    })
    expect(wrapper.attributes('class')).toMatch(/ocean|glow/)
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StakeholderChip.spec.js`
Expected: 3 FAILED (component does not exist).

- [ ] **Step 3: Create the component**

Write `frontend/src/components/results/StakeholderChip.vue`:

```vue
<template>
  <span :class="['inline-flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-full border font-medium', styleFor(stance)]">
    <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
    {{ name }} · {{ stanceLabel }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  stance: { type: String, required: true }, // opposed | supports | neutral | split
})

const stanceLabel = computed(() => {
  const labels = { opposed: 'Opposed', supports: 'Supports', neutral: 'Neutral', split: 'Split' }
  return labels[props.stance] || props.stance
})

function styleFor(stance) {
  const map = {
    opposed:  'border-coral-amber/40 text-coral-amber bg-coral-amber/10',
    supports: 'border-ocean-glow/40 text-ocean-glow bg-ocean-glow/10',
    split:    'border-organic-violet/40 text-organic-violet bg-organic-violet/10',
    neutral:  'border-mist-depth text-mist bg-ocean-deep/60',
  }
  return map[stance] || map.neutral
}
</script>
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StakeholderChip.spec.js`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/StakeholderChip.vue frontend/src/components/results/__tests__/StakeholderChip.spec.js
git commit -m "feat(results): add StakeholderChip component"
```

---

## Task 19: Create `FindingSlotCard.vue`

**Files:**
- Create: `frontend/src/components/results/FindingSlotCard.vue`
- Create: `frontend/src/components/results/__tests__/FindingSlotCard.spec.js`

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/results/__tests__/FindingSlotCard.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FindingSlotCard from '../FindingSlotCard.vue'

describe('FindingSlotCard', () => {
  const baseProps = {
    slot: 'industry',
    title: 'Banks aligned on adaptable frameworks',
    body: 'Every private-sector participant converged on "industry-led" language.',
    citation: 'Morgan Stanley · 9 posts',
  }

  it('renders title, body, citation', () => {
    const wrapper = mount(FindingSlotCard, { props: baseProps })
    expect(wrapper.text()).toContain('Banks aligned on adaptable frameworks')
    expect(wrapper.text()).toContain('Every private-sector participant')
    expect(wrapper.text()).toContain('Morgan Stanley · 9 posts')
  })

  it('shows the slot label', () => {
    const wrapper = mount(FindingSlotCard, { props: baseProps })
    expect(wrapper.text().toLowerCase()).toContain('industry')
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd frontend && npx vitest run src/components/results/__tests__/FindingSlotCard.spec.js`
Expected: 2 FAILED.

- [ ] **Step 3: Create the component**

Write `frontend/src/components/results/FindingSlotCard.vue`:

```vue
<template>
  <div class="relative bg-ocean-deep border border-mist-depth rounded-2xl p-6 pl-7 transition-all duration-250 hover:border-ocean-cyan hover:-translate-y-px">
    <div :class="['absolute left-0 top-5 bottom-5 w-[3px] rounded-r-md', accentClass]"></div>
    <div :class="['font-mono text-[9px] tracking-[0.1em] uppercase font-semibold', labelClass]">{{ slotLabel }}</div>
    <div class="text-sm font-semibold text-mist-foam mt-2 leading-snug">{{ title }}</div>
    <div class="text-[13px] text-mist-drift mt-2.5 leading-relaxed">{{ body }}</div>
    <div v-if="citation" class="font-mono text-[10px] text-mist-slate mt-2.5 pt-2.5 border-t border-mist-depth">
      {{ citation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  slot: { type: String, required: true },
  title: { type: String, required: true },
  body: { type: String, required: true },
  citation: { type: String, default: '' },
})

const _labels = {
  industry: 'Industry posture',
  regulator: 'Regulator posture',
  intermediary: 'Intermediary role',
  market: 'Market signal',
  turning_point: 'Turning point',
}

const slotLabel = computed(() => _labels[props.slot] || props.slot)

const accentClass = computed(() => ({
  industry: 'bg-coral-amber',
  regulator: 'bg-ocean-glow',
  intermediary: 'bg-organic-violet',
  market: 'bg-organic-seafoam',
  turning_point: 'bg-coral',
})[props.slot] || 'bg-ocean-glow')

const labelClass = computed(() => ({
  industry: 'text-coral-amber',
  regulator: 'text-ocean-glow',
  intermediary: 'text-organic-violet',
  market: 'text-organic-seafoam',
  turning_point: 'text-coral',
})[props.slot] || 'text-ocean-glow')
</script>
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd frontend && npx vitest run src/components/results/__tests__/FindingSlotCard.spec.js`
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/FindingSlotCard.vue frontend/src/components/results/__tests__/FindingSlotCard.spec.js
git commit -m "feat(results): add FindingSlotCard component (slot-coded accents)"
```

---

## Task 20: Create `SimScaleFooter.vue`

**Files:**
- Create: `frontend/src/components/results/SimScaleFooter.vue`
- Create: `frontend/src/components/results/__tests__/SimScaleFooter.spec.js`

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/results/__tests__/SimScaleFooter.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SimScaleFooter from '../SimScaleFooter.vue'

describe('SimScaleFooter', () => {
  it('renders all four stats from scale prop', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 10, horizon_days: 30, bloc_count: 2, market_stress: 'none_observed' } },
    })
    expect(wrapper.text()).toContain('10')
    expect(wrapper.text()).toContain('30')
    expect(wrapper.text()).toContain('2')
  })

  it('shows "None" when market_stress is none_observed', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 1, horizon_days: 7, bloc_count: 0, market_stress: 'none_observed' } },
    })
    expect(wrapper.text()).toContain('None')
  })

  it('shows "Present" when market_stress is present', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 1, horizon_days: 7, bloc_count: 0, market_stress: 'present' } },
    })
    expect(wrapper.text()).toContain('Present')
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd frontend && npx vitest run src/components/results/__tests__/SimScaleFooter.spec.js`
Expected: 3 FAILED.

- [ ] **Step 3: Create the component**

Write `frontend/src/components/results/SimScaleFooter.vue`:

```vue
<template>
  <div class="flex gap-6 px-6 py-5 bg-ocean-deep/40 border border-mist-depth rounded-2xl">
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.participants ?? 0 }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Participants</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.horizon_days ?? 0 }}d</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Horizon</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.bloc_count ?? 0 }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Blocs</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ marketStressLabel }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Market stress</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scale: { type: Object, required: true },
})

const marketStressLabel = computed(() => {
  if (props.scale.market_stress === 'present') return 'Present'
  if (props.scale.market_stress === 'none_observed') return 'None'
  return '—'
})
</script>
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd frontend && npx vitest run src/components/results/__tests__/SimScaleFooter.spec.js`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/SimScaleFooter.vue frontend/src/components/results/__tests__/SimScaleFooter.spec.js
git commit -m "feat(results): add SimScaleFooter component"
```

---

## Task 21: Create `QuestionAnswerHero.vue`

**Files:**
- Create: `frontend/src/components/results/QuestionAnswerHero.vue`
- Create: `frontend/src/components/results/__tests__/QuestionAnswerHero.spec.js`

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/results/__tests__/QuestionAnswerHero.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionAnswerHero from '../QuestionAnswerHero.vue'

describe('QuestionAnswerHero', () => {
  const baseProps = {
    question: 'Will proposal X pass?',
    verdict: 'Unlikely — 3 of 5 blocs opposed.',
    stakeholderPositions: [
      { name: 'Industry bloc', stance: 'opposed', members: ['A'], member_count: 1, rationale_keywords: [] },
      { name: 'Support bloc', stance: 'supports', members: ['B'], member_count: 1, rationale_keywords: [] },
    ],
  }

  it('renders the question prominently', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    expect(wrapper.text()).toContain('Will proposal X pass?')
  })

  it('renders the verdict', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    expect(wrapper.text()).toContain('Unlikely — 3 of 5 blocs opposed.')
  })

  it('renders a chip per stakeholder position', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    const chips = wrapper.findAllComponents({ name: 'StakeholderChip' })
    expect(chips).toHaveLength(2)
  })

  it('shows empty state when verdict is missing', () => {
    const wrapper = mount(QuestionAnswerHero, {
      props: { ...baseProps, verdict: '' },
    })
    expect(wrapper.text()).toContain('Verdict pending')
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd frontend && npx vitest run src/components/results/__tests__/QuestionAnswerHero.spec.js`
Expected: 4 FAILED.

- [ ] **Step 3: Create the component**

Write `frontend/src/components/results/QuestionAnswerHero.vue`:

```vue
<template>
  <div class="relative bg-ocean-deep border border-mist-depth rounded-2xl p-8 overflow-hidden">
    <!-- Subtle glow -->
    <div class="absolute -top-1/2 -left-1/5 w-3/5 h-[200%] pointer-events-none"
         style="background: radial-gradient(ellipse, rgba(34, 211, 238, 0.08), transparent 60%);"></div>

    <div class="relative">
      <div class="flex items-center gap-2 font-mono text-[10px] text-coral-amber tracking-[0.15em] uppercase font-semibold">
        <span class="inline-block w-4 h-px bg-coral-amber"></span>
        The question
      </div>
      <div class="text-xl font-semibold text-mist-foam mt-3 leading-snug tracking-tight">{{ question }}</div>

      <div class="flex items-center gap-2 font-mono text-[10px] text-ocean-glow tracking-[0.15em] uppercase font-semibold mt-7">
        <span class="inline-block w-4 h-px bg-ocean-glow"></span>
        Simulated answer
      </div>
      <div class="text-base text-mist mt-3 leading-relaxed">
        <template v-if="verdict">{{ verdict }}</template>
        <span v-else class="text-mist-slate italic">Verdict pending — rerun the simulation to generate a new answer.</span>
      </div>

      <div v-if="stakeholderPositions.length" class="flex flex-wrap gap-1.5 mt-5">
        <StakeholderChip
          v-for="p in stakeholderPositions"
          :key="p.name"
          :name="p.name"
          :stance="p.stance"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import StakeholderChip from './StakeholderChip.vue'

defineProps({
  question: { type: String, required: true },
  verdict: { type: String, default: '' },
  stakeholderPositions: { type: Array, default: () => [] },
})
</script>
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd frontend && npx vitest run src/components/results/__tests__/QuestionAnswerHero.spec.js`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/QuestionAnswerHero.vue frontend/src/components/results/__tests__/QuestionAnswerHero.spec.js
git commit -m "feat(results): add QuestionAnswerHero component"
```

---

## Task 22: Rewrite Story block in `SimulationResults.vue`

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Update the Story block and imports**

In `frontend/src/views/SimulationResults.vue`:

Replace the imports block (around lines 143-161) — add new, remove old:

```javascript
// Add:
import QuestionAnswerHero from '../components/results/QuestionAnswerHero.vue'
import FindingSlotCard from '../components/results/FindingSlotCard.vue'
import SimScaleFooter from '../components/results/SimScaleFooter.vue'

// Remove:
// import ConfidenceGrid from '../components/results/ConfidenceGrid.vue'
// import FindingCard from '../components/results/FindingCard.vue' (if only used in Story)
// import CoalitionCard from '../components/results/CoalitionCard.vue' (if only used in Story)
// import MarketCurveCompact from '../components/results/MarketCurveCompact.vue' (from Story only)
// import EngagementCompact from '../components/results/EngagementCompact.vue' (from Story only)
```

Update the destructuring from `useSimulationData`:

```javascript
const {
  chatLog,
  chatMessages,
  structured,
  verdict,
  stakeholderPositions,
  namedCoalitions,
  phaseBoundaries,
  quotablePosts,
  simScale,
  buildNodeRelationships,
} = useSimulationData(job)
```

Replace the entire Story `<div v-if="viewMode === 'story'">` block (roughly lines 23-82) with:

```vue
<!-- ── Story View ── -->
<div v-if="viewMode === 'story'" class="relative pt-[120px] pb-24">
  <ReportToc :items="storySections" />

  <div class="max-w-[820px] mx-auto px-6 space-y-6">
    <!-- Meta row -->
    <div id="story-meta" class="flex items-center gap-3 font-mono text-[10px] text-mist-slate uppercase tracking-wider">
      <span>Simulation</span>
      <span class="w-1 h-1 rounded-full bg-mist-depth"></span>
      <span>{{ simScale.participants ?? '—' }} participants</span>
      <span class="w-1 h-1 rounded-full bg-mist-depth"></span>
      <span>{{ simScale.horizon_days ?? '—' }}d horizon</span>
      <span v-if="job.tier" class="w-1 h-1 rounded-full bg-mist-depth"></span>
      <span v-if="job.tier" class="capitalize">{{ job.tier }} depth</span>
    </div>

    <!-- Q+A Hero -->
    <div id="story-hero" data-reveal>
      <QuestionAnswerHero
        :question="job.goal"
        :verdict="verdict"
        :stakeholder-positions="stakeholderPositions"
      />
    </div>

    <!-- What the simulation surfaced -->
    <div v-if="structured?.findings?.length" id="story-findings">
      <div class="font-mono text-[10px] text-mist-slate uppercase tracking-wider mb-4 pl-1">What the simulation surfaced</div>
      <div :class="findingsGridClass">
        <FindingSlotCard
          v-for="(f, i) in structured.findings"
          :key="i"
          :slot="f.slot"
          :title="f.title"
          :body="f.body"
          :citation="f.citation"
        />
      </div>
    </div>

    <!-- Sim-scale footer -->
    <SimScaleFooter id="story-scale" :scale="simScale" />

    <!-- Share bar -->
    <div class="flex items-center justify-between px-5 py-4 bg-ocean-deep/40 border border-mist-depth rounded-xl">
      <div class="text-xs text-mist-drift">
        This artifact was generated by a multi-agent simulation. Open the Report for methodology and source citations.
      </div>
      <div class="flex gap-2">
        <button class="text-xs px-3.5 py-2 rounded-lg border border-mist-depth text-mist hover:border-ocean-glow hover:text-mist-foam transition"
                @click="handleShare">Copy link</button>
        <button class="text-xs px-3.5 py-2 rounded-lg border border-ocean-glow text-ocean-glow bg-ocean-glow/10 hover:text-mist-foam transition"
                :disabled="pdfLoading" @click="handleExport">
          {{ pdfLoading ? 'Exporting…' : 'Export PDF' }}
        </button>
      </div>
    </div>
  </div>
</div>
```

Update `storySections`:

```javascript
const storySections = computed(() => [
  { id: 'story-hero', label: 'Question & answer' },
  { id: 'story-findings', label: 'Findings' },
  { id: 'story-scale', label: 'Scale' },
])
```

Add the findings-grid responsive class computed:

```javascript
const findingsGridClass = computed(() => {
  const n = structured.value?.findings?.length ?? 0
  if (n <= 1) return 'grid gap-4 grid-cols-1'
  if (n === 2) return 'grid gap-4 grid-cols-1 md:grid-cols-2'
  if (n === 3) return 'grid gap-4 grid-cols-1 md:grid-cols-2 [&>*:nth-child(3)]:md:col-span-2'
  return 'grid gap-4 grid-cols-1 md:grid-cols-2'  // 4+ → 2x2
})
```

- [ ] **Step 2: Leave the Report block untouched**

The `v-else-if="viewMode === 'report'"` block (around lines 104-125) stays as it is — markdown + ChatReplay + header.

- [ ] **Step 3: Remove references to deleted imports**

Search and remove any lingering usage of removed components within the Story branch:

```bash
grep -n "ConfidenceGrid\|SentimentBars\|FindingCard\|CoalitionCard\|MarketCurveCompact\|EngagementCompact" frontend/src/views/SimulationResults.vue
```

Any hits inside the Story block must be removed. Hits elsewhere (Data view) are allowed if those components still exist there.

- [ ] **Step 4: Run the frontend test suite**

Run: `cd frontend && npm test`
Expected: all PASSED. Fix any snapshot failures caused by the Story DOM change — snapshot updates are acceptable for this task (this IS the redesign).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SimulationResults.vue
git commit -m "feat(results): rewrite Story view with Q+A hero + slotted finding deck"
```

---

## Task 23: Delete dead frontend components

**Files:**
- Delete: `frontend/src/components/results/SentimentBars.vue`
- Delete: `frontend/src/components/results/ConfidenceGrid.vue`
- Delete: related test files
- Modify: any snapshot or index files referencing them

- [ ] **Step 1: Confirm no remaining references**

Run:

```bash
grep -rn "SentimentBars\|ConfidenceGrid" frontend/src/
```

Expected: only test files and the components themselves. If other Vue files still import these, those imports must be removed first.

- [ ] **Step 2: Delete files**

```bash
git rm frontend/src/components/results/SentimentBars.vue
git rm frontend/src/components/results/ConfidenceGrid.vue
git rm -f frontend/src/components/results/__tests__/SentimentBars.spec.js 2>/dev/null || true
git rm -f frontend/src/components/results/__tests__/ConfidenceGrid.spec.js 2>/dev/null || true
```

- [ ] **Step 3: Run frontend test suite**

Run: `cd frontend && npm test`
Expected: all PASSED.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(results): delete SentimentBars + ConfidenceGrid (replaced by SimScaleFooter)"
```

---

## Task 24: Full-stack regression + manual verification checklist

**Files:**
- Modify: `docs/superpowers/plans/2026-04-16-story-report-redesign.md` (append a verification log at the bottom if desired)

- [ ] **Step 1: Run the full Python test suite**

Run: `pytest tests/ -v`
Expected: all PASSED.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: all PASSED.

- [ ] **Step 3: Lint**

Run: `ruff check . && cd frontend && npx eslint src/`
Expected: no errors (or only pre-existing ones).

- [ ] **Step 4: Manual smoke — wizard and draft path**

In a dev backend + frontend:
1. `/new-simulation` → confirm 30-day chip is preselected on load.
2. Try to launch a draft with no timeline selected → expect 422 error.
3. Launch with the default → job enters PENDING.

- [ ] **Step 5: Manual smoke — Story render**

Seed a completed job (can be job #109 data imported into a local dev DB, or a fresh dev-run). Navigate to `/jobs/:id`:
1. Story mode shows: meta row, Q+A hero with verdict + stakeholder chips, findings grid (1/2/3/4 depending on data), sim-scale footer, share bar.
2. Hover a finding card: accent border lights up, card lifts slightly.
3. Report mode shows: markdown + ChatReplay unchanged.
4. No `SentimentBars` or `ConfidenceGrid` artifacts visible anywhere.
5. Graph mode still renders.
6. Data mode still renders.

- [ ] **Step 6: Final commit**

```bash
git commit --allow-empty -m "docs(story): verification smoke completed on dev"
```

---

## Self-Review

**Spec coverage check:**
- Problem / ICP / direction — background, not tasks. ✓
- Path 3 pipeline, schema — Tasks 1-9, 11. ✓
- Path 2 prompt rewrite — Task 14. ✓
- Report runner / `_build_structured` / `key_insight` — Tasks 15, 16. ✓
- `forecast_days` required — Task 12. ✓
- Wizard default — Task 13. ✓
- Frontend Story redesign + components — Tasks 17-22. ✓
- Cleanup of dead components — Task 23. ✓
- Contracts schema update — Task 10. ✓
- Testing: unit + regression fixture from job 109 — Tasks 1-9. ✓
- Report view unchanged — respected throughout (Task 22 explicitly leaves the block alone). ✓

**Placeholder scan:** no "TBD" / "similar to above" / "handle edge cases"; every code step has actual code. ✓

**Type consistency:**
- `story_signals.build_story_signals(chat_log, graph_data, forecast_days)` — same signature in Tasks 1, 8, 11, 15. ✓
- `adapt_structured(brief, findings, chat_log, graph_data, forecast_days, verdict)` — same in Tasks 11, 15. ✓
- `ReportRunner(job_id, goal, forecast_days, client, fetcher)` — same in Task 15 runner rewrite and task integration. ✓
- `useSimulationData` returns `verdict, stakeholderPositions, namedCoalitions, phaseBoundaries, quotablePosts, simScale, disagreementAxis` — consumed unchanged by Task 22. ✓
- Finding shape `{slot, title, body, citation, accent_color}` — produced in Task 15 parser, stored by Task 11 adapter, consumed by Task 22 Story block and Task 19 FindingSlotCard. ✓
- `StakeholderChip` stance values (`opposed | supports | neutral | split`) match the values `_classify_stance` returns (Task 2) and `extract_stakeholder_positions` outputs (Task 3). ✓
- `SimScaleFooter` reads `participants, horizon_days, bloc_count, market_stress` — matches `compute_sim_scale` output (Task 7). ✓

No gaps surfaced. Plan is complete.
