# Graph Entity Sentiment Scoring — Design Spec

**Date:** March 29, 2026
**GitHub Issue:** #25
**Goal:** Add per-entity sentiment scores (-1.0 to +1.0) to graph nodes, derived from chat_log content analysis using a keyword lexicon.

---

## 1. Architecture

New `score_entity_sentiment()` function in `infra/docker/run_job.py`, called after `extract_graph_data()` and `collect_chat_log()`. Attaches a `sentiment` float to each node in the graph_data dict before serialization. No LLM calls — pure text analysis using a positive/negative keyword lexicon.

The frontend already renders sentiment (colors, glows, sizing, tooltips, legend, grouping toggle). Only the backend data is missing.

---

## 2. Sentiment Scoring Algorithm

### Input
- `graph_data["nodes"]` — list of entity dicts with `uuid`, `name`, `labels`, `summary`
- `chat_log` — list of agent action dicts with `agent_name`, `action_type`, `action_args.content`

### Steps

1. **Build keyword lexicon** — ~50 positive words ("support", "praise", "agree", "benefit", "success", "approve", "welcome") and ~50 negative words ("oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn", "attack", "ban").

2. **For each graph node**, scan all chat_log entries where:
   - The node's `name` appears (case-insensitive) in `action_args.content`, OR
   - The `agent_name` matches the node's `name` (agent IS the entity)

3. **For each matching entry**, count positive and negative keyword hits in the content text.

4. **Compute score:**
   ```
   if positive + negative == 0: sentiment = 0.0
   else: sentiment = (positive - negative) / (positive + negative)
   ```
   Clamp to [-1.0, +1.0].

5. **Average across all mentions** for that entity. If no mentions found, sentiment = 0.0.

6. **Attach** `sentiment` field to each node dict in `graph_data["nodes"]`.

### Output
```json
{"uuid": "...", "name": "Trump", "labels": ["PoliticalFigure"], "summary": "...", "sentiment": -0.35, "connection_count": 5}
```

---

## 3. Keyword Lexicon

Stored as module-level constants in `run_job.py`:

```python
POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success", "agree",
    "positive", "progress", "growth", "improve", "achieve", "gain", "boost",
    "encourage", "optimistic", "favorable", "advance", "strengthen", "celebrate",
    "endorse", "commend", "constructive", "prosper", "thrive", "cooperate",
    "alliance", "partnership", "diplomatic", "peaceful", "stable", "recovery",
    "innovation", "opportunity", "confident", "resolve", "protect", "invest",
    "expand", "lead", "unite", "embrace", "recommend", "affirm", "uphold",
    "champion", "reform", "empower", "sustain", "reliable",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy", "collapse",
    "risk", "danger", "decline", "loss", "struggle", "tension", "hostile",
    "aggressive", "escalate", "violate", "disrupt", "undermine", "restrict",
    "protest", "controversy", "criticism", "backlash", "concern", "fear",
    "instability", "vulnerable", "deficit", "recession", "inflation", "corrupt",
    "exploit", "abuse", "negligence", "incompetent", "reckless", "toxic",
    "polarize", "divide", "obstruct", "retaliate", "assassinate",
}
```

---

## 4. Schema Change

In `saas/schemas/graph.py`, add to `GraphNode`:
```python
sentiment: float = 0.0
```

No migration needed — `result_graph` is a JSON text column. The new field is added to the JSON content, not to the DB schema.

---

## 5. Pipeline Integration

In `run_pipeline()`, after `extract_graph_data()` and `collect_chat_log()`:

```python
graph_data = extract_graph_data(graph_id)
score_entity_sentiment(graph_data, chat_log)  # mutates graph_data in place
```

---

## 6. Frontend (already built, no changes needed)

All of these already read `node.sentiment` and render accordingly:
- **GraphCanvas.vue** — sentiment color ring, glow, size scaling
- **GraphControls.vue** — Type/Sentiment grouping toggle
- **GraphLegend.vue** — Positive/Negative/Neutral legend
- **GraphDetailPanel.vue** — sentiment value in properties
- **GraphVisualization.vue** — sentiment in hover tooltip

---

## 7. Testing

- Unit test for `score_entity_sentiment()` with sample graph nodes + chat_log
- Test with no mentions → sentiment 0.0
- Test with positive-only content → sentiment > 0
- Test with negative-only content → sentiment < 0
- Test with mixed content → sentiment between -1 and 1
- Test agent-as-entity matching

---

## 8. Future Improvement: LLM-Based Scoring (Option B)

Replace the keyword lexicon with a single vLLM batch prompt on the GPU pod:

```
Given these agent posts about the following entities, rate the overall sentiment
toward each entity from -1.0 (very negative) to +1.0 (very positive):

Entities: [Trump, Iran, EU Parliament, ...]
Posts: [post1, post2, ...]

Return JSON: {"Trump": -0.4, "Iran": -0.7, ...}
```

**Pros:** More accurate for sarcasm, nuance, context-dependent sentiment.
**Cons:** Adds ~30s to pipeline, depends on vLLM being available after report generation, costs GPU time.
**When to upgrade:** If user feedback indicates keyword-based sentiment is too inaccurate for demos/marketing.
