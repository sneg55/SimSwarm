---
sidebar_label: Story Signals
---

# Story Signals

Story signals are deterministic, LLM-free aggregates extracted from the chat log and entity
graph. They feed both the Story view directly and the `report.j2` prompt as grounding
context (so the report LLM cannot invent entities or events). The conceptual overview is in
[Story signals](../concepts/story-signals.md); this page documents the computation. Sources:
`simswarm/story_signals.py`, `story_signals_scale.py`, `story_signals_constants.py`.

`build_story_signals(chat_log, graph_data, forecast_days)` is the entry point. It returns:

```python
{
  "stakeholder_positions": [...],
  "named_coalitions": [...],
  "phase_boundaries": [...],
  "quotable_posts": [...],
  "disagreement_axis": "<kw> vs <kw>",
  "sim_scale": {...},
}
```

All functions are pure (no I/O, no LLM). `chat_log` is the already-serialized list of
ActionRecord dicts; post body text is read via `extractor_common.post_text` (preferring
`action_args["text"]`, falling back to `["content"]`).

## Stance classification

`_classify_stance(text)` lowercases the text, counts hits from two curated keyword sets, and
returns the dominant side:

- `opposed` if opposed-signal hits exceed support hits
- `supports` if the reverse
- `split` on a non-zero tie
- `neutral` when neither set matches

The keyword sets live in `story_signals_constants.py`. `OPPOSED_SIGNALS` and
`SUPPORT_SIGNALS` are conservative frozensets curated from production goals. Representative
opposed signals: `oppose`, `against`, `reject`, `block`, `stifle`/`stifling`, `hinder`,
`undue burden`, `overly prescriptive`, `competitive disadvantage`, `protect proprietary`,
`regulatory fragmentation`, `litigation`. Representative support signals: `support`,
`endorse`, `transparency`, `accountability`, `oversight`, `investor protection`,
`standardized reporting`, `market integrity`, `systemic resilience`, `regulatory clarity`.
A post matching neither set is intentionally neutral.

> These sets were hand-tuned against real corpora — e.g. industry blocs resisting SEC AI
> disclosure rarely say "oppose" outright but reuse a recurring defensive vocabulary
> (observed in prod job 109). Treat the lists as authoritative; don't paraphrase them.

`_agent_dominant_stance(posts)` reduces a single agent to one stance: it tallies per-post
classifications, drops `neutral` when any directional stance exists, and returns the top
directional stance (or `split` on a tie among directional stances).

## Stakeholder positions and coalitions

`extract_stakeholder_positions` groups agents (by their `agent_name`) on their dominant
stance, considering only `create_post` / `create_comment` actions. Each bucket becomes a
position dict with `name` (from `STANCE_BLOC_NAME`, e.g. "Opposition bloc"), `stance`,
sorted `members`, `member_count`, and `rationale_keywords` (top 3 tokens via `_top_keywords`,
with the stance vocabulary excluded so "oppose" doesn't become a bloc's keyword). Positions
are sorted `opposed, supports, split, neutral`.

`name_coalitions(positions)` promotes any position with **≥2 members** to a named coalition.
The name prefers a keyword-derived form (`"{keyword.capitalize()}-focused {stance} group"`)
and falls back to a `COALITION_LABEL` value.

## Phase boundaries

`extract_phase_boundaries(chat_log, forecast_days)` chunks the run by round number:

- If `max_round < 3`: a single `"Full horizon"` phase spanning rounds `[1, max_round]`.
- Otherwise: three phases labeled `Early`, `Mid`, `Late`, splitting rounds and forecast days
  into thirds. Each phase carries a `week_range` (`_days_to_week_range`, 1-indexed weeks of
  7 days) and a `dominant_topic` (the single top keyword across that phase's posts).

This is why the report prompt insists on phase/week language rather than round numbers — the
phase mapping is the engine's chosen unit of narrative time.

## Quotable posts

`extract_quotable_posts(chat_log, phases, graph_data)` picks the highest-engagement
`create_post` per `(phase, stance)` cell, deduped so each agent is quoted at most once.
Engagement is a heuristic count (`_engagement_for_post`): `like_post`/`repost` actions whose
`action_args["target_post"]` contains the marker `f"{agent_id}_r{round_num}"`. Each selected
quote carries `agent_name`, `agent_role` (first non-`Entity` graph label via `_role_map`),
`phase`, `text`, and `engagement`.

> **Caveat (native runs):** these marker and arg names don't appear in native social-env
> logs — that env emits `vote`/`repost` actions keyed by `post_id`, not `like_post`/`target_post`
> with an `{agent_id}_r{round}` marker — so `_engagement_for_post` is effectively always 0 and
> selection degenerates to the first post seen per `(phase, stance)` cell. Likewise `_role_map`
> reads node keys `name`/`labels`, but `build_graph` nodes use `label`/`group`
> (`graph.py:122-130`), so `agent_role` is always empty on native runs.

## Disagreement axis and sim scale

These live in `story_signals_scale.py` and are re-exported through `story_signals`.

`extract_disagreement_axis(chat_log)` collects `opposed` vs `supports` post text, takes the
top keyword from each (excluding the stance vocabulary via the combined `OPPOSED_SIGNALS |
SUPPORT_SIGNALS` stopword set), and returns `"<support_kw> vs <opposed_kw>"` — falling back to
whichever single side has a keyword, or `""`.

`compute_sim_scale(chat_log, forecast_days, bloc_count)` returns honest aggregates:

```python
{
  "participants": <distinct agent_names>,
  "horizon_days": forecast_days,
  "bloc_count": bloc_count,
  "market_stress": "present" if any successful buy/sell action else "none_observed",
}
```

`market_stress` is `"present"` only if there is a successful `buy_shares`/`sell_shares`/
`buy`/`sell` action; otherwise `"none_observed"` — the report is instructed to name a calm
market explicitly rather than fabricate trades.

## Shared color map

`story_signals_constants.SLOT_COLORS` maps report slots to hex accents
(`industry → #F97316`, `regulator → #22D3EE`, `intermediary → #A78BFA`, `market → #6EE7B7`,
`turning_point → #FF6B6B`), aligned with the frontend Tailwind tokens. It is re-exported from
`story_signals` so the SaaS report layer can tag findings without duplicating the mapping.
