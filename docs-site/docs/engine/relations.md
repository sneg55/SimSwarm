---
sidebar_label: Relations
---

# Entity Relations

After a run, SimSwarm derives **typed semantic edges** between entities by re-reading a
sample of the transcript with the smart LLM. These edges (`DISAGREES_WITH`, `SUPPORTS`,
`RESPONDS_TO`, …) restore the knowledge-graph relations the frontend Graph tab used to get
from the pre-cutover Graphiti pipeline. They are merged into the graph via
`build_graph(..., relations=...)` — see [Graph build](graph-build.md). Source:
`simswarm/relations.py`.

## `extract_relations(...)`

```python
async def extract_relations(
    entities: list[Entity],
    chat_log: list[ActionRecord],
    llm: LLMClient,
    *,
    goal: str = "",
    max_posts: int = 60,
    max_relations: int = 30,
) -> list[dict]:
```

Returns a list of `{"source", "target", "type", "fact"}` dicts where `source`/`target` are
entity **names** (callers map names to ids when building edges). It short-circuits to `[]`
if there are no entities or no posts.

### 1. Sample posts — the `text` key contract

`_sample_posts` walks the chat log for `create_post` records and reads the body with
`post_text(r.action_args)` from `simswarm/extractor_common.py`. That helper is the single
source of truth for post-body access:

```python
def post_text(action_args: dict | None) -> str:
    if not action_args:
        return ""
    return str(action_args.get("text") or action_args.get("content") or "")
```

The native social environment stores bodies under `text` (see
`environments/social.py:_handle_create_post`); older fixtures use `content`. Always use
`post_text()` in new extractors rather than reaching into `action_args` directly.

Each sampled post is `{"author": r.agent_name or r.agent_id, "content": ...}`. Using the
display **name** (not the snake_case id) is deliberate: showing ids biased the LLM into
echoing ids back as `source`/`target`, which then failed name filtering and dropped every
relation (the sim #112 regression). The prompt now shows one consistent naming style.

### 2. Prompt and parsing

The `extract_relations.j2` template lists the valid entity names, the goal, and the sampled
posts, then asks for up to `max_relations` directed relations as a pure JSON array with
`source`, `target`, `type`, `fact`.

`_call_and_parse` performs **one call plus a single repair retry**: it calls the LLM at
`temperature=0.2`, and on a parse failure it logs a 500-char preview of the raw response
(previously swallowed — see sim #128), appends a stricter "reply with ONLY a JSON array"
instruction, and retries at `temperature=0.0`. A second failure raises
`RelationExtractionError`. `_parse_json_array` strips markdown fences and slices between the
first `[` and last `]` before `json.loads`.

### 3. Filtering — drop unknown endpoints

`_build_canonical_name_lookup` maps any plausible variant the LLM might emit
(`entity.name`, lowered name, `entity.id`, lowered id) back to the canonical `entity.name`,
earliest entry winning on collision. Then each parsed row is filtered:

- `source`, `target`, and `type` must be non-empty (type is uppercased).
- Both endpoints must resolve through the canonical lookup.
- **Self-loops are dropped** (`src == tgt`).
- `type` is truncated to 40 chars, `fact` to 400.

If `data` was non-empty but every row was filtered out, a `relations.empty_after_filter`
warning logs the raw response preview so a silent zero-edge regression is diagnosable from
logs without re-running. A final `relations.extracted` log records the count and the distinct
relation types.

## Where it runs

Relation extraction runs **on-pod**, in the job runner immediately after `Engine.run`
returns, on the smart LLM — outside the engine's own loop (`Engine.run` builds the graph
with interaction edges only). The runner (`infra/docker/run_job_v2_runner.py`) then passes
the extracted relations to `build_graph(entities, chat_log, relations=...)` to produce the
final relation-merged graph with both interaction and semantic edges, all before the GPU pod
is torn down. Only report generation runs off-pod, after the pod uploads its artifacts.
