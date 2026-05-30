---
sidebar_label: Graph Build
---

# Graph build

`simswarm/graph.py` constructs the entity graph the frontend renders in Cytoscape. It is
pure Python. It takes the entity list the sim ran on plus the `ActionRecord` chat log and
returns a `GraphSnapshot` (`{nodes, edges, metadata}`). It replaces an earlier Neo4j-backed
ingestion path.

## `build_graph(entities, chat_log, relations=None)`

```python
def build_graph(
    entities: list[Entity],
    chat_log: list[ActionRecord],
    relations: list[dict] | None = None,
) -> GraphSnapshot:
```

1. `_build_nodes(entities, chat_log)`: one node per entity.
2. `id_by_name = {node["label"]: node["id"]}`: name→id lookup.
3. `_build_post_author_index(chat_log)`: maps `post_id` → authoring `agent_id`.
4. `_build_edges(...)`: interaction edges from the chat log.
5. If `relations` is provided, `_relations_to_edges(...)` appends the LLM semantic edges.
6. `metadata` records `total_nodes`, `total_edges`, `total_rounds`, and sorted
   `entity_types`.

The engine's own `Engine.run` calls `build_graph(entities, chat_log)` without relations
(interaction edges only); the LLM semantic edges are merged on-pod by the job runner
(`infra/docker/run_job_v2_runner.py`) right after `Engine.run` returns, before the GPU pod is
torn down (see [Relations](relations.md)).

## Nodes

`_build_nodes` first precomputes per-agent stats from the chat log (`total_actions`,
`total_posts` for `create_post`/`post`/`comment`, and the set of active rounds). Each entity
becomes:

```python
{"id": entity.id, "label": entity.name, "group": entity.type,
 "summary": entity.summary, "total_actions": ..., "total_posts": ...,
 "rounds_active": <len(rounds set)>}
```

## Interaction edges

`_build_edges` tallies directed `(source_id, target_id, type)` triples and collapses repeats
into a single edge with `weight = count`. Only successful actions are considered.

### Action-type → edge label

```python
_INTERACTION_ACTIONS = {
    "follow": "follow", "reply": "reply",
    "like": "like", "like_post": "like",
    "repost": "repost", "retweet": "repost",
    "quote": "quote", "mention": "mention",
    "vote": "like",   # special-cased below
}
```

`vote` is special-cased: the edge label becomes `like` when `action_args["value"] >= 0`,
otherwise `dislike` (non-numeric values default to `1` → like).

### Target resolution

`_resolve_target` walks `_TARGET_ARG_KEYS` in order, first non-empty match wins:

```python
("target_id", "target_agent", "target_name", "target",
 "to", "recipient", "post_author", "agent_id", "post_id")
```

- `post_id` is resolved through the **post→author index**: `reply`/`repost`/`vote` actions
  whose only reference is a post UUID are mapped back to the post's author. The author must
  be a known agent id.
- A raw value matching a known agent id is used directly.
- A raw value matching an entity name (e.g. `target_name="Yann LeCun"`) maps through
  `id_by_name`.

Self-edges (`target_id == agent_id`) are never created.

## Mention detection

For post-content actions (`create_post`/`post`/`comment`/`reply`), `_scan_mentions(text,
id_by_name)` finds referenced agents two ways and tallies a `mention` edge for each:

1. **`@handle`:** the regex `@(\w+)` matches single-token handles; each handle is looked up
   in `id_by_name`.
2. **Full-label match:** case-insensitive, word-boundary (`\b...\b`) search for each entity's
   full name, so multi-word names ("US Navy", "Donald Trump") that the `@`-regex misses are
   still caught.

Each distinct target is counted at most once per scan (dedup via a `seen` set), and self
mentions are skipped.

## LLM semantic edges

`_relations_to_edges(relations, id_by_name)` maps the name-keyed relation dicts from
[`extract_relations`](relations.md) into id-keyed edges:

```python
{"source": src_id, "target": tgt_id, "type": rtype, "weight": 1, "fact": <optional>}
```

Rows are dropped if either endpoint name fails to map to an id, if the type is empty, or if
the edge is a self-loop. The optional `fact` string (the one-sentence justification) is
carried onto the edge for the Graph tab tooltip.

## Vocabulary-drift caution

Like the extractors, `graph.py` matches `action_type` and `action_args` keys by literal
string. If an environment renames a tool or an argument key, both `_INTERACTION_ACTIONS` /
`_TARGET_ARG_KEYS` here and the relevant extractor must be updated, or edges silently vanish.
Audit this file alongside the extractor family on any env change.
