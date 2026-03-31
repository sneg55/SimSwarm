# MiroShark Engine Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MiroFish + Zep Cloud with MiroShark + self-hosted Neo4j, eliminating the Zep dependency and gaining belief states, round memory, cross-platform awareness, and simulation-aware reports.

**Architecture:** MiroShark replaces MiroFish as the git submodule. A dedicated Hetzner CX22 VPS runs Neo4j 5.15 Community. GPU pods connect to Neo4j via Bolt protocol, use vLLM for NER extraction, and OpenAI for embeddings. The SaaS adapter layer is updated to pass Neo4j credentials instead of Zep API keys.

**Tech Stack:** MiroShark (Python/Flask), Neo4j 5.15 Community (Docker), OASIS/Wonderwall simulation engine, OpenAI embeddings, vLLM for LLM inference

---

## Task 1: Provision Neo4j VPS

**Files:**
- Create: `infra/neo4j/docker-compose.yml`
- Create: `infra/neo4j/setup.sh`

- [ ] **Step 1: Provision Hetzner CX22**

Via Hetzner Cloud console or CLI:
- Location: Falkenstein (close to existing VPS)
- Image: Ubuntu 24.04
- Type: CX22 (4GB RAM, 2 vCPU, 40GB disk)
- SSH key: same as existing VPS (`~/.ssh/simswarm_deploy`)
- Name: `simswarm-neo4j`

Save the IP address.

- [ ] **Step 2: Create Neo4j Docker Compose**

Create `infra/neo4j/docker-compose.yml`:

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    container_name: simswarm-neo4j
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
    ports:
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p ${NEO4J_PASSWORD} 'RETURN 1'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

volumes:
  neo4j_data:
```

- [ ] **Step 3: Create setup script**

Create `infra/neo4j/setup.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Neo4j VPS Setup ==="

# Install Docker
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
fi

# Create directory
mkdir -p /opt/neo4j
cd /opt/neo4j

# Copy compose file
cat > docker-compose.yml << 'COMPOSE'
services:
  neo4j:
    image: neo4j:5.15-community
    container_name: simswarm-neo4j
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    ports:
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p $$NEO4J_PASSWORD 'RETURN 1' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

volumes:
  neo4j_data:
COMPOSE

# Generate password
NEO4J_PASSWORD=$(openssl rand -hex 16)
echo "NEO4J_PASSWORD=${NEO4J_PASSWORD}" > .env
echo "Generated password: ${NEO4J_PASSWORD}"

# Start
docker compose up -d

echo "=== Neo4j ready on port 7687 ==="
echo "Connection: bolt://<this-ip>:7687"
echo "User: neo4j"
echo "Password: ${NEO4J_PASSWORD}"
```

- [ ] **Step 4: Deploy to Neo4j VPS**

```bash
ssh -i ~/.ssh/simswarm_deploy root@<neo4j-vps-ip> 'bash -s' < infra/neo4j/setup.sh
```

Verify:
```bash
ssh -i ~/.ssh/simswarm_deploy root@<neo4j-vps-ip> "cd /opt/neo4j && docker compose ps"
```

- [ ] **Step 5: Configure firewall**

On the Neo4j VPS, allow port 7687 only from the existing VPS and RunPod IP ranges:

```bash
ssh -i ~/.ssh/simswarm_deploy root@<neo4j-vps-ip> "
ufw allow ssh
ufw allow from 178.156.236.185 to any port 7687
ufw allow from 0.0.0.0/0 to any port 7687 comment 'RunPod pods'
ufw --force enable
"
```

Note: RunPod pods have dynamic IPs so we allow 7687 from all for now. Neo4j auth provides the access control.

- [ ] **Step 6: Save credentials**

Add to existing VPS `.env`:
```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "
echo 'NEO4J_URI=bolt://<neo4j-vps-ip>:7687' >> /opt/fishcloud/.env
echo 'NEO4J_USER=neo4j' >> /opt/fishcloud/.env
echo 'NEO4J_PASSWORD=<generated-password>' >> /opt/fishcloud/.env
"
```

Add to GitHub secrets:
```bash
gh secret set NEO4J_URI --body "bolt://<neo4j-vps-ip>:7687"
gh secret set NEO4J_PASSWORD --body "<generated-password>"
```

Add to local `.env.local`:
```bash
echo 'NEO4J_URI=bolt://<neo4j-vps-ip>:7687' >> .env.local
echo 'NEO4J_USER=neo4j' >> .env.local
echo 'NEO4J_PASSWORD=<generated-password>' >> .env.local
```

- [ ] **Step 7: Test connectivity from existing VPS**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "
pip install neo4j 2>/dev/null
python3 -c \"
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://<neo4j-vps-ip>:7687', auth=('neo4j', '<password>'))
with d.session() as s:
    r = s.run('RETURN 1 AS n')
    print('Neo4j OK:', r.single()['n'])
d.close()
\"
"
```

- [ ] **Step 8: Commit infra files**

```bash
git add infra/neo4j/
git commit -m "infra: Neo4j VPS setup script and docker-compose"
```

---

## Task 2: Fork MiroShark and swap git submodule

**Files:**
- Modify: `.gitmodules`
- Remove: `vendor/mirofish/` (submodule)
- Add: `vendor/miroshark/` (submodule)

- [ ] **Step 1: Fork MiroShark to own GitHub account**

```bash
gh repo fork aaronjmars/MiroShark --clone=false
```

This creates `sneg55/MiroShark` — we own the fork regardless of upstream activity.

- [ ] **Step 2: Remove MiroFish submodule**

```bash
git submodule deinit -f vendor/mirofish
git rm -f vendor/mirofish
rm -rf .git/modules/vendor/mirofish
```

- [ ] **Step 3: Add MiroShark submodule**

```bash
git submodule add https://github.com/sneg55/MiroShark.git vendor/miroshark
git submodule update --init --recursive
```

- [ ] **Step 4: Verify MiroShark structure**

```bash
ls vendor/miroshark/backend/app/storage/
# Should show: __init__.py, graph_storage.py, neo4j_storage.py, ner_extractor.py, embedding_service.py, search_service.py, neo4j_schema.py

ls vendor/miroshark/backend/app/services/
# Should show: ontology_generator.py, simulation_manager.py, report_agent.py, entity_reader.py, graph_builder.py, graph_tools.py, etc.

ls vendor/miroshark/backend/scripts/
# Should show: run_parallel_simulation.py, round_memory.py, cross_platform_digest.py, belief_integration.py, etc.
```

- [ ] **Step 5: Commit**

```bash
git add .gitmodules vendor/miroshark
git commit -m "feat: replace MiroFish submodule with MiroShark fork"
```

---

## Task 3: Rebuild worker Docker image for MiroShark

**Files:**
- Modify: `infra/docker/Dockerfile.worker`
- Modify: `infra/docker/start.sh`
- Delete: `infra/docker/graphiti/` (all shadow modules)

- [ ] **Step 1: Update Dockerfile.worker**

Rewrite `infra/docker/Dockerfile.worker`:

```dockerfile
# GPU Worker Image for FishCloud
# Based on vLLM's official image (has CUDA + vLLM + correct transformers pre-installed)
FROM vllm/vllm-openai:v0.6.6.post1 AS base

USER root
WORKDIR /app

# Save vLLM's pinned dependency versions
RUN pip freeze > /tmp/vllm-freeze.txt

# Install MiroShark dependencies
COPY vendor/miroshark/backend/requirements.txt /app/miroshark-requirements.txt
RUN pip install --no-cache-dir --ignore-installed -r /app/miroshark-requirements.txt || true

# Install worker deps
RUN pip install --no-cache-dir --ignore-installed flask flask-cors requests neo4j openai

# Restore vLLM's critical pinned versions
RUN grep -E "^(transformers|tokenizers|starlette|fastapi|uvicorn|numpy)==" /tmp/vllm-freeze.txt > /tmp/vllm-restore.txt && \
    pip install --no-cache-dir --force-reinstall -r /tmp/vllm-restore.txt

# Verify all imports + numpy<2 (vLLM ABI requirement)
RUN python3 -c "import vllm; print(f'vLLM {vllm.__version__}')" && \
    python3 -c "import numpy; v=numpy.__version__; print(f'numpy {v}'); assert int(v.split('.')[0]) < 2, f'numpy {v} >= 2.0 breaks vLLM'" && \
    python3 -c "import flask; print(f'Flask OK')" && \
    python3 -c "import neo4j; print(f'neo4j OK')"

# Copy MiroShark engine
COPY vendor/miroshark/backend/ /app/miroshark/backend/

# Copy our job runner and worker API
COPY infra/docker/run_job.py /app/run_job.py
COPY infra/docker/worker_api.py /app/worker_api.py
COPY infra/docker/start.sh /app/start.sh
RUN chmod +x /app/run_job.py /app/start.sh

RUN mkdir -p /tmp/results /tmp/seed

EXPOSE 5000 8000

ENTRYPOINT []
CMD ["/bin/bash", "/app/start.sh"]
```

- [ ] **Step 2: Delete shadow modules**

```bash
rm -rf infra/docker/graphiti/
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker/Dockerfile.worker infra/docker/start.sh
git rm -rf infra/docker/graphiti/
git commit -m "feat: rebuild worker Dockerfile for MiroShark + Neo4j, remove Graphiti shadows"
```

---

## Task 4: Rewrite run_job.py for MiroShark pipeline

**Files:**
- Rewrite: `infra/docker/run_job.py`

This is the largest task. The new `run_job.py` calls MiroShark services instead of MiroFish services.

- [ ] **Step 1: Rewrite run_job.py**

The new pipeline flow:

```python
# 1. Setup
setup_miroshark_config()          # write .env for MiroShark
sys.path.insert(0, MIROSHARK_BACKEND)

# 2. Build graph
storage = Neo4jStorage(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD,
                       embedding_service=embedding_svc, ner_extractor=ner)
ontology = OntologyGenerator().generate(document_texts=[seed_text], simulation_requirement=goal)
graph_id = storage.create_graph(name=f"SimSwarm-{int(time.time())}")
storage.set_ontology(graph_id, ontology)
chunks = TextProcessor.split_text(seed_text, chunk_size=500, overlap=50)
storage.add_text_batch(graph_id, chunks, batch_size=3)

# 3. Prepare simulation
sm = SimulationManager()
state = sm.create_simulation(project_id=graph_id, graph_id=graph_id,
                             enable_twitter=True, enable_reddit=True)
sm.prepare_simulation(simulation_id=state.simulation_id,
                      simulation_requirement=goal, document_text=seed_text,
                      storage=storage)

# 4. Run simulation
SimulationRunner.start_simulation(simulation_id=state.simulation_id,
                                 platform="parallel", max_rounds=max_rounds)
# Poll run_state until complete

# 5. Generate report
graph_tools = GraphToolsService(storage=storage)
agent = ReportAgent(graph_id=graph_id, simulation_id=state.simulation_id,
                    simulation_requirement=goal, graph_tools=graph_tools)
report = agent.generate_report()

# 6. Collect results
chat_log = SimulationRunner.get_all_actions(simulation_id)
graph_data = storage.get_graph_data(graph_id)

# 7. Cleanup
storage.delete_graph(graph_id)
storage.close()
```

Key differences from MiroFish's run_job.py:
- `Neo4jStorage` replaces `GraphBuilderService` + `ZepToolsService` + `ZepEntityReader`
- `storage` object is passed to `prepare_simulation()` and `GraphToolsService`
- No Zep polling (`wait_for_episodes` is a no-op — Neo4j writes are synchronous)
- No shadow module injection
- No Chinese prompt patching (MiroShark is already English)
- Keep: seed enrichment, English ontology prompt override, platform profile patching
- Remove: `_inject_shadow_modules()`, `_patch_mirofish_prompts_to_english()`

The full implementation should follow the structure of the existing `run_job.py` but replace all MiroFish service calls with MiroShark equivalents. The enrichment step stays as-is (it's our own code).

- [ ] **Step 2: Run backend tests**

```bash
python -m pytest tests/ -x -q --ignore=tests/test_graphiti_shadow.py
```

Note: graphiti shadow tests should be deleted (Task 3 removes the shadow modules). Many tests mock at the Celery level and won't be affected.

- [ ] **Step 3: Commit**

```bash
git add infra/docker/run_job.py
git commit -m "feat: rewrite run_job.py for MiroShark pipeline (Neo4j + Wonderwall)"
```

---

## Task 5: Update SaaS layer — config, JobConfig, tasks

**Files:**
- Modify: `saas/config.py`
- Modify: `saas/workers/job_runner.py`
- Modify: `saas/workers/tasks.py`
- Modify: `saas/api/jobs.py`
- Modify: `infra/scripts/run_demos.py`

- [ ] **Step 1: Add Neo4j settings to config**

In `saas/config.py`, add:

```python
    # Neo4j graph database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
```

- [ ] **Step 2: Update JobConfig**

In `saas/workers/job_runner.py`, update `JobConfig`:

Replace `openai_api_key` field with `neo4j_uri`, `neo4j_user`, `neo4j_password` fields.

Update `to_worker_env()` (renamed from `to_mirofish_env()`):

```python
    def to_worker_env(self) -> dict[str, str]:
        return {
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": "http://localhost:8000/v1",
            "LLM_MODEL_NAME": self.model_id,
            "NEO4J_URI": self.neo4j_uri,
            "NEO4J_USER": self.neo4j_user,
            "NEO4J_PASSWORD": self.neo4j_password,
            "OPENAI_API_KEY": self.openai_api_key,
            "OASIS_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
            "MODEL_ID": self.model_id,
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "EMBEDDING_DIMENSIONS": "1536",
        }
```

- [ ] **Step 3: Update tasks.py**

In `saas/workers/tasks.py`, add `neo4j_uri`, `neo4j_user`, `neo4j_password` parameters to `run_simulation_task` and pass them to `JobConfig`.

- [ ] **Step 4: Update jobs.py**

In `saas/api/jobs.py`, update `run_simulation_task.delay()` to pass Neo4j credentials from env:

```python
neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
```

- [ ] **Step 5: Update run_demos.py**

In `infra/scripts/run_demos.py`, update `dispatch_demo()` to pass Neo4j credentials.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/ -x -q --ignore=tests/test_graphiti_shadow.py
```

Fix any tests that reference old field names (`zep_api_key`, `to_mirofish_env`).

- [ ] **Step 7: Commit**

```bash
git add saas/config.py saas/workers/job_runner.py saas/workers/tasks.py saas/api/jobs.py infra/scripts/run_demos.py
git commit -m "feat: update SaaS layer for MiroShark — Neo4j config, JobConfig, task dispatch"
```

---

## Task 6: Update deploy pipeline

**Files:**
- Modify: `.github/workflows/deploy.yml`
- Modify: `deploy.sh`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update deploy.yml**

In `.github/workflows/deploy.yml`, the deploy step needs to pass `NEO4J_*` env vars. The current deploy script reads from `.env` on the server, which already has the Neo4j credentials from Task 1. No changes needed to the workflow — the `.env` file is the source of truth.

However, update the Dockerfile reference from `vendor/mirofish` to `vendor/miroshark`.

- [ ] **Step 2: Update docker-compose.yml**

In `docker-compose.yml`, the celery service env section — add Neo4j vars:

```yaml
    environment:
      - DATABASE_URL=postgresql+asyncpg://fishcloud:${POSTGRES_PASSWORD}@db:5432/fishcloud
      - REDIS_URL=redis://redis:6379/0
      - NEO4J_URI=${NEO4J_URI}
      - NEO4J_USER=${NEO4J_USER:-neo4j}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
```

Same for the `app` service.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml deploy.sh docker-compose.yml
git commit -m "feat: update deploy pipeline for MiroShark + Neo4j"
```

---

## Task 7: Clean up old code

**Files:**
- Delete: `tests/test_graphiti_shadow.py`
- Delete: `docs/superpowers/specs/2026-03-30-graphiti-kuzu-migration.md`
- Delete: `docs/superpowers/plans/2026-03-30-graphiti-kuzu-migration.md`
- Modify: `CLAUDE.md` — update references from MiroFish to MiroShark
- Modify: `README.md` — update engine references

- [ ] **Step 1: Delete Graphiti-related files and tests**

```bash
rm -f tests/test_graphiti_shadow.py
```

- [ ] **Step 2: Update CLAUDE.md**

Replace references to `vendor/mirofish/` with `vendor/miroshark/`. Update the repository layout section. Update the adapter description.

- [ ] **Step 3: Update README.md**

Update the architecture section, project structure, and any MiroFish references to MiroShark.

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -x -q
cd frontend && npm test -- --run
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: clean up MiroFish/Graphiti references, update docs for MiroShark"
```

---

## Task 8: End-to-end test and deploy

- [ ] **Step 1: Verify Neo4j VPS is healthy**

```bash
ssh -i ~/.ssh/simswarm_deploy root@<neo4j-vps-ip> "cd /opt/neo4j && docker compose ps"
```

- [ ] **Step 2: Push to main and verify CI**

```bash
git push origin main
# Wait for CI: Tests + Build Worker Image + Deploy to Hetzner
gh run list --limit 3
```

- [ ] **Step 3: Verify deployment**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "
grep WORKER_IMAGE_TAG /opt/fishcloud/.env
grep NEO4J_URI /opt/fishcloud/.env
curl -sf http://localhost:8080/api/health
"
```

- [ ] **Step 4: Run a test simulation via the browser**

Log in as the test user and create a small tier simulation. Verify:
- Enrichment works (Web Research card appears)
- GPU pod provisions
- Pipeline runs (status transitions: Queued → Allocating GPU → Running)
- Report generates
- Graph visualization works
- Results page loads

- [ ] **Step 5: Run demo simulations**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "
cd /opt/fishcloud
docker compose exec -T celery python infra/scripts/run_demos.py --slugs tesla-earnings --parallel
"
```

- [ ] **Step 6: Monitor for orphaned pods**

```bash
# Wait 30 min, then check
RUNPOD_API_KEY=... python3 -c "import runpod; runpod.api_key='...'; print(len(runpod.get_pods()), 'pods')"
```

- [ ] **Step 7: Close related GitHub issues**

```bash
gh issue close 52 -c "Resolved by MiroShark migration — Neo4j replaces Zep Cloud"
gh issue close 53 -c "Resolved by MiroShark migration — custom NER + Neo4j graph"
```
