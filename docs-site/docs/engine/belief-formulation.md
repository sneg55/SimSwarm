---
sidebar_label: Belief Formulation
---

# Belief Formulation

Belief dynamics are what make a SimSwarm run more than a transcript. They are implemented in
`simswarm/belief.py` as **pure math — no LLM calls**. The conceptual overview lives in
[Beliefs & stance](../concepts/beliefs-and-stance.md); this page documents the exact
formula and every coefficient as it appears in the code.

## Module constants

These are the literal values from `simswarm/belief.py`:

```python
EXPOSURE_CAP = 2000
DEFAULT_TRUST = 0.5
NOVELTY_NEW = 1.5
NOVELTY_REPEAT = 0.5
SOCIAL_PROOF_FLOOR = 0.3
SOCIAL_PROOF_PER_LIKE = 0.07
CONFIDENCE_BOOST_PER_LIKE = 0.005
CONFIDENCE_DECAY_PER_DISLIKE = 0.008
TRUST_LEARNING_RATE = 0.05
```

## State

A `BeliefState` (`simswarm/types.py`) holds three dicts and one set:

- `positions`: topic → position in `[-1.0, 1.0]`
- `confidence`: topic → confidence in `[0.0, 1.0]`
- `trust`: author name → trust in `[0.0, 1.0]`
- `exposure_history`: a set of content hashes (deduplication for novelty)

## `update_beliefs(state, posts, topic, own_likes=0, own_dislikes=0)`

Returns a **new** `BeliefState` (the input is deep-copied, never mutated). `posts` is a list
of dicts with `author`, `content_hash`, `stance` (`[-1, 1]`), and `likes`.

### 1. Resistance divisor

```python
current_pos  = state.positions.get(topic, 0.0)
current_conf = state.confidence.get(topic, 0.5)
resistance = 0.3 + current_conf * 0.7   # range: 0.3 (low conf) … 1.0 (high conf)
```

Higher confidence yields a larger divisor, so a more confident agent moves less per unit of
influence.

### 2. Per-post influence and pull-toward-stance

For each exposed post:

```python
seen_before = content_hash in state.exposure_history
novelty = NOVELTY_REPEAT if seen_before else NOVELTY_NEW   # 0.5 vs 1.5
state.exposure_history.add(content_hash)                   # mark seen

trust = state.trust.get(author, DEFAULT_TRUST)             # 0.5 for unknown authors
social_proof = SOCIAL_PROOF_FLOOR + likes * SOCIAL_PROOF_PER_LIKE   # 0.3 + 0.07*likes

influence = trust * social_proof * novelty / resistance

gap = stance - current_pos
position_delta += gap * influence * 0.1
```

The **social-proof floor** (`0.3`) ensures even zero-engagement posts register some
influence. **Novelty** rewards first exposure (`1.5`) over repeats (`0.5`). The
**pull-toward-stance** nudge is proportional to the `gap` between the post's stance and the
agent's current position, scaled by `influence` and a fixed `0.1`.

### 3. Apply and clamp position

```python
new_pos = current_pos + position_delta
state.positions[topic] = max(-1.0, min(1.0, new_pos))
```

### 4. Trust evolution

After the position update, every observed author's trust is adjusted toward agreement with
the agent's *resulting* position:

```python
alignment = 1.0 - abs(stance - new_position) / 2.0     # 1 = same, 0 = polar opposite
trust_delta = (alignment - 0.5) * TRUST_LEARNING_RATE  # ±0.025 at the extremes
trust[author] = max(0.0, min(1.0, trust[author] + trust_delta))
```

Authors aligned with the agent gain trust (toward `1.0`); opposed authors lose it. Unknown
authors are first seeded at `DEFAULT_TRUST = 0.5`.

### 5. Confidence update from own engagement

Confidence moves only from engagement on the agent's *own* posts this round:

```python
conf_delta = own_likes * CONFIDENCE_BOOST_PER_LIKE - own_dislikes * CONFIDENCE_DECAY_PER_DISLIKE
#            own_likes * 0.005                       - own_dislikes * 0.008
state.confidence[topic] = max(0.0, min(1.0, current_conf + conf_delta))
```

Dislikes erode confidence slightly faster than likes build it.

### 6. Exposure cap

If `exposure_history` exceeds `EXPOSURE_CAP = 2000`, the oldest entries (by set iteration
order) are discarded down to the cap.

## Engine integration: `apply_belief_updates`

The engine calls `apply_belief_updates(agents, round_records, topic, likes_lookup=...)` once
per round, after action dispatch. It mutates each `Agent.belief_state` in place.

1. **Collect posts.** It keeps successful records whose `action_type.lower()` is one of
   `create_post`, `post`, `comment`, `reply`. Post text is read from
   `action_args["text"]` (falling back to `["content"]`); empty text is skipped.
2. **Score and hash.** Stance comes from `simswarm.stance.score_stance(text)` (VADER — see
   [Stance scoring](stance-scoring.md)). The content hash is
   `f"r{round}:{agent_id}:{hash(text) & 0xffffffff:08x}"`.
3. **Look up engagement.** `post_id` is read from the action's `action_result`; likes and
   dislikes are looked up in `likes_lookup` (built from each social env's
   `current_engagement()`), defaulting to `(0, 0)`.
4. **Build exposures per agent.** For each agent, exposures are all posts authored by
   *other* agents (an agent never influences itself), and `own_likes`/`own_dislikes` are the
   summed engagement on its own posts. Agents with no exposures and zero own-engagement are
   skipped entirely.
5. **Update.** `agent.belief_state = update_beliefs(state, posts=exposures, topic=topic,
   own_likes=..., own_dislikes=...)`.

The resulting positions and confidence feed back into the agent's next-round system prompt
via `render_beliefs` in `simswarm/llm.py`, which maps the numeric position/confidence to
English bands (e.g. "strongly opposed", "firmly held") so the LLM acts consistently with its
evolving beliefs.
