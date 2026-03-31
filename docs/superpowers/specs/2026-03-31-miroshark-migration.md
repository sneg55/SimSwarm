# MiroShark Engine Swap

## Problem

Zep Cloud free plan is hard-blocked (episode limit exceeded). Every attempt to replace it (Graphiti+Kuzu) has failed due to driver bugs. MiroFish's graph pipeline is the bottleneck. Meanwhile MiroShark — a 10-day-old fork of MiroFish — has already solved all these problems with a custom Neo4j implementation, plus adds belief states, cross-platform awareness, round memory, and simulation-aware reports.

## Solution

Replace MiroFish with MiroShark as the simulation engine. Spin up a dedicated Hetzner CX22 VPS for Neo4j. Rebuild the worker Docker image around MiroShark. Update the SaaS adapter layer. One branch, one cutover.

## Architecture

```
Hetzner VPS 1 (existing)          Hetzner VPS 2 (new, CX22)
├── FastAPI app                    └── Neo4j 5.15 Community
├── Celery + Redis                     (bolt://neo4j-vps:7687)
├── PostgreSQL 16                      4GB RAM, 2 vCPU
├── Caddy
└── connects to Neo4j VPS ──────────────────┘

RunPod GPU Pods (ephemeral)
├── vLLM (Qwen 32B AWQ)
├── MiroShark engine (Wonderwall)
├── worker_api.py (Flask)
└── connects to Neo4j VPS over internet
```

- **Neo4j** runs on dedicated CX22 VPS (~$4.50/mo), accessible via Bolt protocol
- **GPU pods** connect to Neo4j over the internet (Bolt is low-latency, small payloads)
- **SaaS layer** stays on existing VPS, connects to Neo4j for graph extraction
- **MiroShark** replaces MiroFish as git submodule in `vendor/`

## What Changes

### Git Submodule

Replace `vendor/mirofish/` with `vendor/miroshark/` pointing to `https://github.com/aaronjmars/MiroShark`.

### Neo4j VPS

- Hetzner CX22: 4GB RAM, 2 vCPU, 40GB disk
- Docker Compose with single service: `neo4j:5.15-community`
- Auth: `NEO4J_AUTH=neo4j/<generated_password>`
- Ports: 7687 (Bolt) exposed, 7474 (browser) internal only
- Firewall: allow 7687 only from existing VPS IP + RunPod IP ranges
- Volume: `neo4j_data:/data` for persistence

### Worker Docker Image

Replace MiroFish with MiroShark:

```dockerfile
# Instead of:
COPY vendor/mirofish/backend/ /app/mirofish/backend/

# Now:
COPY vendor/miroshark/backend/ /app/miroshark/backend/
```

Dependencies change:
- Remove: `zep-cloud` (no longer needed at all)
- Remove: `graphiti-core`, `kuzu` (failed experiment)
- Add: `neo4j>=5.15.0` (already in MiroShark's requirements)
- Keep: `camel-ai`, `flask`, `openai`, `vllm` base image

MiroShark bundles Wonderwall (OASIS fork) directly — no `camel-oasis==0.2.5` force-install needed.

Remove shadow modules: `infra/docker/graphiti/` (no longer needed).

### run_job.py

Rewrite to call MiroShark's pipeline instead of MiroFish's:

```python
MIROSHARK_BACKEND = "/app/miroshark/backend"

# MiroShark services replace MiroFish services:
from app.storage.neo4j_storage import Neo4jStorage
from app.storage.ner_extractor import NERExtractor
from app.services.ontology_generator import OntologyGenerator
from app.services.entity_reader import EntityReader
from app.services.simulation_manager import SimulationManager
from app.services.report_agent import ReportAgent
```

Key differences:
- `Neo4jStorage` takes `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` env vars
- NER extraction uses the on-pod vLLM (same LLM_BASE_URL)
- Embeddings use OpenAI `text-embedding-3-small` (same OPENAI_API_KEY)
- No Zep polling — Neo4j writes are synchronous
- Report agent has `simulation_feed` tool — reads actual agent posts
- Platform-specific prompts built in — remove our monkey-patches

### Environment Variables

Remove:
- `ZEP_API_KEY` (everywhere)

Add:
- `NEO4J_URI=bolt://<neo4j-vps-ip>:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=<generated>`

Keep:
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME`
- `OPENAI_API_KEY` (for embeddings)
- `XAI_API_KEY` (for seed enrichment)
- `RUNPOD_API_KEY`, `STRIPE_*`, etc.

### SaaS Layer Changes

`saas/workers/job_runner.py`:
- `JobConfig.to_mirofish_env()` → `to_worker_env()`: remove ZEP_API_KEY, add NEO4J_* vars
- Remove `zep_api_key` field from JobConfig

`saas/workers/tasks.py`:
- Remove `zep_api_key` parameter (already done in Graphiti migration)
- Pipeline stage inference may need updating for MiroShark log messages

`saas/config.py`:
- Add `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` settings
- Keep `ZEP_API_KEY` as optional (for backward compat during transition)

`infra/docker/run_job.py`:
- Complete rewrite of graph building + simulation pipeline
- Remove all Zep-related code
- Remove shadow module injection
- Remove MiroFish prompt monkey-patches (MiroShark already English, already has platform prompts)
- Keep: seed enrichment, platform profile patching (if still needed), ontology generation

### Frontend

No changes needed. The SaaS API layer abstracts the engine. Graph data, chat logs, reports, and structured results all flow through the same schemas.

### What We Can Delete

- `infra/docker/graphiti/` (all 6 shadow module files)
- Zep-related monkey patches in `run_job.py`
- Platform prompt patches in `run_job.py` (MiroShark has them built in)
- `saas/workers/enrichment.py` stays (xAI enrichment is our addition, not engine-dependent)

## Migration Steps

1. Provision Neo4j CX22 VPS
2. Set up Neo4j Docker + firewall
3. Replace git submodule (mirofish → miroshark)
4. Rebuild worker Docker image
5. Rewrite `run_job.py` for MiroShark pipeline
6. Update `JobConfig` env vars
7. Test end-to-end on a worktree branch
8. Cut over: merge, deploy, verify

## Risk Mitigation

- **Bus factor**: Fork MiroShark to `sneg55/MiroShark` so we own the code regardless
- **Rollback**: Keep MiroFish submodule tag, can revert worker image tag to `9fcd016`
- **Neo4j VPS down**: Worker pods will fail gracefully (connection refused → job failed → refund). Add health check monitoring.
- **Data migration**: None needed — graphs are ephemeral, rebuilt per job

## Cost

| Item | Current | After |
|------|---------|-------|
| Zep Cloud | Free (broken) | $0 (removed) |
| Neo4j VPS | $0 | ~$4.50/mo |
| OpenAI embeddings | ~$0.001/job | ~$0.001/job (same) |
| GPU pods | ~$0.86/hr | ~$0.86/hr (same) |
| **Net** | Blocked | **+$4.50/mo, working** |

## Timeline

~1-2 weeks for full implementation and testing.
