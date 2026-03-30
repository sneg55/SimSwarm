# Graphiti + Kuzu Migration: Replace Zep Cloud

## Problem

Zep Cloud is on a free plan that hit its episode usage limit and 5 req/s rate limit. Simulations fail with `403: Account is over the episode usage limit`. The graph is the report agent's only data source — without it, the entire pipeline is broken.

## Solution

Replace the `zep-cloud` SDK with `graphiti-core` + Kuzu (embedded graph DB) running in-process on the GPU pod. Shadow modules intercept MiroFish's Zep imports so the engine code stays untouched.

## Architecture

```
GPU Pod Process
  ├── vLLM (Qwen 32B) — LLM for entity extraction + simulation
  ├── Kuzu (in-memory) — embedded graph DB, zero infra
  ├── Graphiti (graphiti-core) — graph framework, uses vLLM + OpenAI embedder
  └── MiroFish pipeline — unchanged, shadow modules intercept Zep calls
```

- **LLM for entity extraction:** vLLM on the pod via `OpenAIGenericClient(base_url="http://localhost:8000/v1")`
- **Embeddings:** OpenAI `text-embedding-3-small` via `OPENAI_API_KEY` env var
- **Graph isolation:** Each job gets a fresh `KuzuDriver(db=':memory:')` instance
- **No Zep dependency:** Remove `zep-cloud` from worker image, remove `ZEP_API_KEY` from job config
- **No fallback:** Hard-cut to Graphiti (Zep free plan is already broken)

## Shadow Module Strategy

Three files in `infra/docker/graphiti/` replace three Zep service files. Injected via `sys.path` ordering before MiroFish imports:

```python
# In run_job.py, before any MiroFish imports
sys.path.insert(0, "/app/graphiti")   # shadow modules first
sys.path.insert(1, MIROFISH_BACKEND)  # real MiroFish second
```

When MiroFish does `from app.services.graph_builder import GraphBuilderService`, Python finds our shadow version.

### Shadow modules

| Shadow file | Replaces | Classes |
|------------|----------|---------|
| `graphiti/__init__.py` | — | `get_graphiti_instance()` singleton factory |
| `graphiti/graph_builder.py` | `app.services.graph_builder` | `GraphBuilderService` |
| `graphiti/zep_tools.py` | `app.services.zep_tools` | `ZepToolsService` |
| `graphiti/zep_entity_reader.py` | `app.services.zep_entity_reader` | `ZepEntityReader` |
| `graphiti/zep_paging.py` | `app.utils.zep_paging` | `fetch_all_nodes()`, `fetch_all_edges()` |

### Shared Graphiti instance

`graphiti/__init__.py` provides a lazy singleton:

```python
_instance = None

async def get_graphiti_instance() -> Graphiti:
    global _instance
    if _instance is None:
        driver = KuzuDriver(db=':memory:')
        llm_client = OpenAIGenericClient(config=LLMConfig(
            api_key="not-needed",
            model=os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct-AWQ"),
            base_url="http://localhost:8000/v1",
        ))
        embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
        ))
        _instance = Graphiti(graph_driver=driver, llm_client=llm_client, embedder=embedder)
    return _instance
```

## API Mapping: Zep Cloud → Graphiti

### GraphBuilderService

| Zep method | Graphiti equivalent |
|-----------|-------------------|
| `client.graph.create(graph_id, name)` | Create `KuzuDriver(':memory:')` + `Graphiti()` instance, use `group_id` for logical isolation |
| `client.graph.set_ontology(graph_ids, entities, edges)` | Store `entity_types` and `edge_types` dicts for passing to `add_episode()` calls |
| `client.graph.add_batch(graph_id, episodes)` | Loop `graphiti.add_episode(name, episode_body, source, reference_time, entity_types, edge_types)` |
| `client.graph.episode.get(uuid_)` for polling | No-op — `add_episode()` is synchronous, returns when processing is done |
| `client.graph.delete(graph_id)` | `await clear_data(driver)` or let instance be garbage collected |

### ZepToolsService

| Zep method | Graphiti equivalent |
|-----------|-------------------|
| `client.graph.search(graph_id, query, scope, reranker)` | `graphiti.search_(query, config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER, group_ids=[group_id])` |
| `get_all_nodes()` via `fetch_all_nodes()` | `EntityNode.get_by_group_ids(driver, [group_id])` |
| `get_all_edges()` via `fetch_all_edges()` | `EntityEdge.get_by_group_ids(driver, [group_id])` |

### ZepEntityReader

| Zep method | Graphiti equivalent |
|-----------|-------------------|
| `fetch_all_nodes(client, graph_id)` | `EntityNode.get_by_group_ids(driver, [group_id])` |
| `fetch_all_edges(client, graph_id)` | `EntityEdge.get_by_group_ids(driver, [group_id])` |
| `client.graph.node.get_entity_edges(node_uuid)` | `EntityEdge.get_by_group_ids(driver, [group_id])` filtered by source/target UUID |
| `client.graph.node.get(uuid_)` | `EntityNode.get_by_uuid(driver, uuid)` |

### zep_paging.py

| Zep method | Graphiti equivalent |
|-----------|-------------------|
| `fetch_all_nodes(client, graph_id)` with cursor pagination | `EntityNode.get_by_group_ids(driver, [group_id])` — no pagination needed, all data is local |
| `fetch_all_edges(client, graph_id)` with cursor pagination | `EntityEdge.get_by_group_ids(driver, [group_id])` — no pagination needed |

## Data Flow

```
1. run_job.py starts → shadow modules injected into sys.path

2. build_graph(seed_text, goal)
   ├── OntologyGenerator.generate() → vLLM call (unchanged)
   ├── GraphBuilderService.create_graph()
   │   └── Creates Graphiti(KuzuDriver(':memory:'), llm=vLLM, embedder=OpenAI)
   ├── GraphBuilderService.set_ontology()
   │   └── Stores entity_types + edge_types dicts for add_episode calls
   └── GraphBuilderService.add_text_batches()
       └── graphiti.add_episode() per chunk (synchronous, no polling)

3. prepare_simulation()
   └── ZepEntityReader.filter_defined_entities()
       └── EntityNode.get_by_group_ids() + filter by labels

4. run_and_wait() — no graph access

5. generate_report()
   └── ZepToolsService tools query the graph:
       ├── search_graph() → graphiti.search_()
       ├── get_all_nodes() → EntityNode.get_by_group_ids()
       └── get_all_edges() → EntityEdge.get_by_group_ids()

6. extract_graph_data()
   ├── get_all_nodes/edges → dump to JSON
   └── Graphiti instance garbage collected
```

## Ontology Translation

Zep's `set_ontology()` takes `EntityModel` and `EdgeModel` classes. Graphiti takes `dict[str, type[BaseModel]]`. The shadow `GraphBuilderService.set_ontology()` translates:

```python
# Zep ontology format (from OntologyGenerator):
{
    "entity_types": [{"name": "Person", "description": "...", "attributes": [...]}],
    "edge_types": [{"name": "WORKS_FOR", "source_targets": [...]}]
}

# Translated to Graphiti format:
entity_types = {"Person": PersonModel}  # dynamically created Pydantic models
edge_types = {"WORKS_FOR": WorksForModel}
edge_type_map = {("Person", "Organization"): ["WORKS_FOR"]}
```

The shadow module dynamically creates Pydantic `BaseModel` subclasses from the ontology dict, with fields matching the declared attributes.

## Worker Docker Image Changes

### Remove
- `zep-cloud==3.13.0` from worker requirements
- `ZEP_API_KEY` from worker env vars

### Add
- `graphiti-core>=0.28.0` to worker requirements
- `kuzu>=0.4.0` to worker requirements
- `OPENAI_API_KEY` env var (for embeddings only)
- `infra/docker/graphiti/` directory (5 shadow module files)

### Env var changes in job config

In `saas/workers/job_runner.py` `JobConfig.to_mirofish_env()`:
- Remove `ZEP_API_KEY`
- Add `OPENAI_API_KEY` (for embeddings)

## Error Handling

- `add_episode()` failure: catch, retry once, skip chunk on second failure. One missing chunk is acceptable.
- OpenAI embedder unreachable: search degrades to non-vector. Keep `_local_search()` fallback.
- Kuzu OOM (unlikely at 50-200MB): job fails with clear error, same as Zep API failure today.

## Testing

- Shadow modules get unit tests with real Kuzu in-memory — no mocks needed.
- Test each shadow class against the interface MiroFish expects.
- One integration test: full `build_graph → extract_graph_data` flow with small seed text.
- `graphiti-core` and `kuzu` added to dev dependencies for local testing.
- No changes to existing tests — they mock at the Celery task level.

## Performance Impact

| Operation | Zep Cloud (current) | Graphiti + Kuzu |
|-----------|-------------------|-----------------|
| Text ingestion | 60-120s (API + internal NER) | 30-90s (local, still needs LLM) |
| Episode polling | 60-180s (3s poll interval) | 0s (synchronous) |
| Entity filtering | 10-30s (API + rate limits) | 1-5s (local queries) |
| Graph search | 1-3s per query (API) | <100ms per query (local) |
| **Total graph phase** | **~3-6 min** | **~1-2 min** |

Net: ~2-4 minutes saved per job. At $0.86/hr pod cost, saves ~$0.03-0.06 per job.

## Cost Impact

| Item | Zep Cloud (current) | Graphiti + Kuzu |
|------|-------------------|-----------------|
| Zep API | Free (but broken at limit) | $0 |
| OpenAI embeddings | $0 | ~$0.001/job |
| GPU pod time | Same | ~2-4 min less |
| **Net** | Blocked | **~$0.001/job** |

## Files to Create/Modify

### Create (in worktree `infra/docker/graphiti/`)
- `__init__.py` — Graphiti singleton factory
- `graph_builder.py` — Shadow `GraphBuilderService`
- `zep_tools.py` — Shadow `ZepToolsService`
- `zep_entity_reader.py` — Shadow `ZepEntityReader`
- `zep_paging.py` — Shadow paging utilities

### Modify
- `infra/docker/run_job.py` — inject shadow module path
- `infra/docker/Dockerfile.worker` — add `graphiti-core`, `kuzu`, remove `zep-cloud`
- `infra/docker/requirements-worker.txt` (or equivalent) — dependency changes
- `saas/workers/job_runner.py` — remove `zep_api_key` from `JobConfig.to_mirofish_env()`, add `OPENAI_API_KEY`
- `saas/workers/tasks.py` — stop passing `zep_api_key`
- `saas/config.py` — add `OPENAI_API_KEY` setting

### Test files to create
- `tests/test_graphiti_shadow.py` — unit tests for shadow modules
