---
sidebar_label: Stance Scoring
---

# Stance Scoring

Belief updates need a numeric stance for every post. SimSwarm derives it deterministically
with VADER — no LLM call, so it is fast, cheap, and reproducible. The implementation is
`simswarm/stance.py`.

## The scorer

```python
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_VADER = SentimentIntensityAnalyzer()

def score_stance(text: str) -> float:
    """Return a stance score in [-1.0, 1.0] from VADER's compound score."""
    if not text:
        return 0.0
    return _VADER.polarity_scores(text)["compound"]
```

- **Input:** a post body string.
- **Output:** VADER's `compound` score, a float in `[-1.0, 1.0]`. Empty text scores `0.0`.
- **Determinism:** the analyzer is a module-level singleton; given the same text it always
  returns the same score. VADER handles negation, intensifiers, and punctuation internally.

The dependency is pinned (`vaderSentiment==3.3.2` in `pyproject.toml`) and the lexicon is
warmed in the worker Dockerfile so the first call on a fresh pod doesn't pay a load penalty.

## Where it is used

- **Belief loop** — `simswarm/belief.py` calls `score_stance(text)` to assign the `stance`
  field on each exposed post before computing the pull-toward-stance nudge. See
  [Belief formulation](belief-formulation.md).
- **Agent trajectories** — `simswarm/extractor_activity.py` (`extract_agent_trajectories`)
  scores each agent's combined per-round post/comment text with `score_stance` to produce
  the `sentiment` value charted on the Data tab.

## Two distinct scorers — don't confuse them

There are **two** sentiment functions in the engine with different purposes and scales:

| Function | Module | Method | Scale | Used by |
|---|---|---|---|---|
| `score_stance` | `stance.py` | VADER compound | `[-1, 1]` | belief loop, trajectories |
| `score_sentiment` | `extractor_common.py` | keyword bag `(pos - neg) / total_words` | clamped `[-1, 1]` | legacy extractor sentiment arcs |

The keyword bag (`POSITIVE_WORDS` / `NEGATIVE_WORDS` in `extractor_common.py`) is a lighter,
pre-VADER scorer that remains only because its specific scaling drives the extractor's
per-agent `sentiment_arc` formatting. The belief loop standardized on VADER; do not route
new belief-side scoring through the keyword scorer.

This is separate again from `story_signals._classify_stance`, which is a *categorical*
keyword classifier (`opposed`/`supports`/`neutral`/`split`) used for bloc clustering — see
[Story signals](story-signals.md). Three different mechanisms, three different jobs.
