---
sidebar_label: Extractors
---

# Extractors

Extractors turn the raw `ActionRecord` chat log into the structured JSON the frontend Data
tab renders. They are pure functions, grouped into sibling modules and re-exported from
`simswarm/extractor.py` so callers keep importing `from simswarm.extractor import ...`.

```python
from simswarm.extractor import (
    extract_posts, extract_top_posts,
    extract_engagement_summary, extract_agent_trajectories, extract_profiles,
    agent_sentiment_from_trajectories,
    extract_social_graph, extract_market_data,
)
```

## Shared helpers: `extractor_common.py`

The shared module holds action-type predicates and the post-body accessor. All extractors
read post text through `post_text(action_args)`, which prefers `action_args["text"]` and
falls back to `["content"]` (the social env writes bodies under `text`; older fixtures use
`content`). Predicates: `is_post` (`create_post`), `is_like` (`like_post`), `is_comment`
(`create_comment`), `is_follow` (`follow`), `is_trade` (`buy_shares`/`sell_shares`). It also
houses `score_sentiment` (the legacy keyword-bag scorer; see [Stance scoring](stance-scoring.md)).

## Posts: `extractor_posts.py`

`extract_posts(chat_log)` returns one dict per `create_post` record:
`agent_id`, `agent_name`, `platform`, `content`, `round_num`, `action_type`, `timestamp`,
`success`.

`extract_top_posts(chat_log, limit=20)` ranks posts by engagement. It stamps each post with a
stable `post_id` (preferring an explicit id from `action_result["post_id"]` /
`action_args["post_id"]` / `["id"]`, else a synthetic `f"{agent_id}-r{round}-{counter}"`),
then tallies likes, dislikes, shares, and comments from actions whose
`action_args["post_id"]` or `["target_id"]` matches. `vote` direction follows the social env:
`value > 0` is a like, anything else (including `0`, missing, or non-numeric) is a dislike.
Output fields: `post_id`, `agent_id`, `agent_name`, `platform`, `content`, `round_num`,
`timestamp`, `num_likes`, `num_dislikes`, `num_shares` (reposts **plus** comments),
`engagement` (`num_likes + num_shares`), sorted descending, truncated to `limit`.

## Activity: `extractor_activity.py`

- `extract_engagement_summary(chat_log)`: per-round metrics: `round`, `total_posts`,
  `total_likes` (with `vote` direction matching `extract_top_posts`), `total_comments`,
  `active_agents`.
- `extract_agent_trajectories(chat_log)`: per-agent `rounds` list of
  `{round, posts, actions, sentiment}`, where `sentiment` is `stance.score_stance` over the
  agent's combined post/comment text that round (VADER, `[-1, 1]`).
- `extract_profiles(chat_log)`: one card per agent: `agent_id`, `name`, `persona` (a
  one-line activity summary; the richer LLM persona is layered on by
  [`personas.py`](personas.md)), `total_posts`, `total_actions`, `rounds_active`, `platforms`.
- `agent_sentiment_from_trajectories(trajectories)`: `{agent_id: mean_sentiment}` (unclamped;
  agents with no rounds skipped).

## Market & social graph: `extractor_market_social.py`

`extract_social_graph(chat_log)` builds follow edges from successful `follow` actions. The
followee id is read from `action_args["agent_id"]` (the engine tool schema's key), falling
back to `["target_id"]` for older logs; the followee name resolves through an id→name map.
Returns `{"edges": [...], "mutual_follows": [...]}`.

`extract_market_data(chat_log)` emits one trade record per `buy_shares`/`sell_shares`. It
reads **executed** values from `action_result` (populated by the engine from the env's
`ActionResult.data`) and falls back to `action_args`. Buys expose `cost` (USD spent) and
`shares`; sells expose `proceeds` under the `cost` key so the UI column stays non-negative.
Each record carries a synthetic `trade_id` (`f"{agent_id}-r{round}-{idx}"`), `side`,
`market_id`, `outcome`, `price`, `cost`, `shares`, `amount_requested`, and metadata.

## Observed JSON shapes

These are the keys that downstream consumers actually read:

- **top posts:** `content` (not `text`), `post_id`, `num_likes`, `num_shares`, `engagement`.
- **agent trajectories:** `rounds[].round`, `rounds[].posts`, `rounds[].actions`,
  `rounds[].sentiment`; no per-round stance field.

## Vocabulary-drift caution

Extractors match `action_type` strings and `action_args` keys by literal string. Every
change to an environment's tools must be mirrored here and in `graph.py`. If a social env
renames a vote arg or a market env changes a result key, the matching extractor silently
tallies zeros: no error, just empty charts (the failure mode behind sims 127 and 128). When
auditing an env change, grep both the extractor family and `graph.py` for the affected
action-type and arg-key, and verify the env actually emits the key the extractor reads. Also
beware: sibling extractors with similar names exist, so confirm which one actually runs before
diagnosing a data gap.
