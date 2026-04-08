# Qwen3 Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the simulation pipeline from Qwen2.5-32B-Instruct-AWQ to Qwen3-14B with thinking mode, achieving better quality at ~50% GPU cost.

**Architecture:** Model selection is fully DB-driven via the `model_routing` table — each tier maps to a model_id, gpu_type, and vllm_args. A new alembic migration updates these rows from Qwen2.5-32B to Qwen3-14B. The vLLM base image is upgraded to support Qwen3. GPU fallback chain is updated since the smaller model fits on cheaper GPUs. Qwen3's thinking mode (`/think`) is enabled for batch operations (persona generation, report synthesis) to improve quality via chain-of-thought reasoning, while disabled (`/no_think`) for simulation agent actions to avoid latency overhead. MiroShark's `LLMClient` already strips `<think>` blocks from responses (line 127), so persona/report calls work out of the box. Simulation prompts get `/no_think` prepended to prevent thinking tokens from interfering with tool calling.

**Tech Stack:** vLLM (upgraded), RunPod GPUs, Alembic migrations, Python.

**Issue:** [sneg55/SimSwarm#66](https://github.com/sneg55/SimSwarm/issues/66)

**Scope:** Phase 2 (safe single-model swap) only. Phase 3 (multi-model pipeline) is a design sketch at the end — separate plan after Phase 2 validates.

**Prerequisites:** Phase 1 A/B testing should confirm Qwen3-14B produces acceptable persona/simulation/report quality. This plan assumes that validation is done.

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `infra/docker/Dockerfile.worker` | Upgrade vLLM base image to support Qwen3 |
| Modify | `infra/docker/start.sh` | Update default model fallback |
| Modify | `infra/docker/service_init.py` | Update hardcoded Qwen2.5 default |
| Create | `alembic/versions/o6p7q8r9s0t1_qwen3_model_routing.py` | Migration to update model_routing rows |
| Modify | `saas/gpu/runpod_provider.py` | Update GPU comment and add smaller GPU to fallback |
| Modify | `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py` | Prepend `/no_think` to agent system prompts |
| Modify | `vendor/miroshark/backend/wonderwall/simulations/polymarket/prompts.py` | Prepend `/no_think` to trader system prompts |
| Modify | `vendor/miroshark/backend/app/services/oasis_profile_prompts.py` | Increase max_tokens hint for thinking overhead |
| Test | `tests/test_config.py` | Verify JobConfig produces correct env vars |

---

### Task 1: Upgrade vLLM Base Image

**Files:**
- Modify: `infra/docker/Dockerfile.worker:3`

Qwen3 requires vLLM >= v0.7.0 for full support (architecture registration, chat template). The current image is `v0.6.6.post1`.

- [ ] **Step 1: Update base image**

In `infra/docker/Dockerfile.worker`, change line 3:

```dockerfile
FROM vllm/vllm-openai:v0.8.5.post1 AS base
```

Note: v0.8.5.post1 is the latest stable release that supports Qwen3 (including the MoE Qwen3-30B-A3B for future Phase 3). Check https://github.com/vllm-project/vllm/releases for the latest if this is stale.

- [ ] **Step 2: Update numpy version check**

The numpy<2 check on line 28 may need adjustment if the new vLLM supports numpy 2.x. Read the Dockerfile line 28 and check the new vLLM's numpy requirements. If vLLM v0.8+ supports numpy 2.x, update the assertion:

```dockerfile
RUN python3 -c "import vllm; print(f'vLLM {vllm.__version__}')" && \
    python3 -c "import numpy; print(f'numpy {numpy.__version__}')" && \
    python3 -c "import flask; print('Flask OK')" && \
    python3 -c "import neo4j; print('neo4j OK')" && \
    python3 -c "import openai; print('openai OK')"
```

If vLLM still requires numpy<2, keep the original assertion.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/sneg55/Documents/GitHub/fishandcat
docker build -f infra/docker/Dockerfile.worker -t simswarm-worker:qwen3-test .
```

Verify the build succeeds and all imports pass.

- [ ] **Step 4: Commit**

```bash
git add infra/docker/Dockerfile.worker
git commit -m "chore: upgrade vLLM base image to v0.8.5 for Qwen3 support

Qwen3 models require vLLM >= v0.7.0 for architecture support and chat
template handling. Upgrading from v0.6.6.post1 to v0.8.5.post1.

Part of sneg55/SimSwarm#66"
```

---

### Task 2: Update Default Model Fallbacks

**Files:**
- Modify: `infra/docker/start.sh:15,17`
- Modify: `infra/docker/service_init.py:56,84`

These files have hardcoded `Qwen2.5-32B-Instruct-AWQ` as fallback defaults. While the actual model is always set via environment variables from `ModelRouting`, the defaults should match to avoid confusion if env vars are missing.

- [ ] **Step 1: Update `start.sh`**

In `infra/docker/start.sh`, update lines 15 and 17:

From:
```bash
    --model ${MODEL_ID:-Qwen/Qwen2.5-32B-Instruct-AWQ} \
    ...
    ${VLLM_ARGS:---quantization awq --max-model-len 32768} \
```

To:
```bash
    --model ${MODEL_ID:-Qwen/Qwen3-14B} \
    ...
    ${VLLM_ARGS:---max-model-len 32768} \
```

Note: Qwen3-14B is not quantized (no AWQ variant needed — 14B fits on 40GB VRAM without quantization). The `--quantization awq` flag is removed from the default. The actual vllm_args still come from ModelRouting via the `VLLM_ARGS` env var.

- [ ] **Step 2: Update `service_init.py`**

In `infra/docker/service_init.py`, update line 56 and line 84:

Line 56 — `setup_miroshark_config()`:
```python
        "LLM_MODEL_NAME": os.getenv("LLM_MODEL_NAME", "Qwen3-14B"),
```

Line 84 — `_apply_config_overrides()`:
```python
    Config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-14B")
```

Note: These defaults use the short model name (without `Qwen/` prefix) because MiroShark's Config stores just the model name. The full HuggingFace ID (`Qwen/Qwen3-14B`) is used by vLLM via `MODEL_ID` env var.

- [ ] **Step 3: Commit**

```bash
git add infra/docker/start.sh infra/docker/service_init.py
git commit -m "chore: update default model fallbacks from Qwen2.5-32B to Qwen3-14B

Default fallbacks in start.sh and service_init.py updated to Qwen3-14B.
Actual model is always set via env vars from ModelRouting table.
Removed --quantization awq from defaults (14B doesn't need quantization).

Part of sneg55/SimSwarm#66"
```

---

### Task 3: Create Alembic Migration for Model Routing

**Files:**
- Create: `alembic/versions/o6p7q8r9s0t1_qwen3_model_routing.py`

This migration updates the existing `model_routing` rows to use Qwen3-14B. It's a data migration, not a schema change.

- [ ] **Step 1: Create the migration file**

```python
"""update model_routing to Qwen3-14B

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-06
"""
from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None

# Qwen3-14B: same quality as Qwen2.5-32B at half the compute cost.
# No AWQ quantization needed — 14B fits on 40GB VRAM natively.
# Lower VRAM requirement allows using cheaper GPUs (L40S for all tiers).
QWEN3_MODEL = "Qwen/Qwen3-14B"
QWEN3_VLLM_ARGS = "--max-model-len 32768"

# Previous model for downgrade
QWEN25_MODEL = "Qwen/Qwen2.5-32B-Instruct-AWQ"
QWEN25_VLLM_ARGS = "--quantization awq --max-model-len 32768"


def upgrade() -> None:
    # Update all tiers to Qwen3-14B with cheaper GPU options
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN3_MODEL}',
            vllm_args = '{QWEN3_VLLM_ARGS}',
            gpu_type = 'NVIDIA L40S'
        WHERE sim_tier IN ('small', 'medium', 'large');
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN25_MODEL}',
            vllm_args = '{QWEN25_VLLM_ARGS}',
            gpu_type = 'a100-40gb'
        WHERE sim_tier = 'small';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN25_MODEL}',
            vllm_args = '{QWEN25_VLLM_ARGS}',
            gpu_type = 'h100-80gb'
        WHERE sim_tier IN ('medium', 'large');
    """)
```

- [ ] **Step 2: Verify alembic single head**

```bash
cd /Users/sneg55/Documents/GitHub/fishandcat
python3 -m alembic heads
```

Expected: Single head `o6p7q8r9s0t1`.

- [ ] **Step 3: Write a test for the migration**

Add to `tests/test_migrations.py` (or create it):

```python
"""Test that model routing migration produces correct values."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_model_routing_qwen3(db_session):
    """After migration, all tiers should use Qwen3-14B on L40S."""
    result = await db_session.execute(text("SELECT sim_tier, model_id, gpu_type, vllm_args FROM model_routing"))
    rows = {r.sim_tier: r for r in result.fetchall()}

    for tier in ("small", "medium", "large"):
        assert tier in rows, f"Missing routing for tier {tier}"
        assert rows[tier].model_id == "Qwen/Qwen3-14B"
        assert rows[tier].gpu_type == "NVIDIA L40S"
        assert "--quantization" not in (rows[tier].vllm_args or "")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_migrations.py -v
```

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/o6p7q8r9s0t1_qwen3_model_routing.py tests/test_migrations.py
git commit -m "feat: migrate model_routing from Qwen2.5-32B to Qwen3-14B

Updates all tier routing to Qwen/Qwen3-14B on NVIDIA L40S GPUs.
Qwen3-14B matches Qwen2.5-32B quality at half the compute cost.
No AWQ quantization needed (14B fits natively on 48GB L40S VRAM).
All tiers can now use cheaper L40S instead of A100/H100.

Part of sneg55/SimSwarm#66"
```

---

### Task 4: Update GPU Fallback Chain

**Files:**
- Modify: `saas/gpu/runpod_provider.py:39-40`

The GPU fallback chain comment references the 32B AWQ model's VRAM requirements. With Qwen3-14B, we need less VRAM and should prefer cheaper GPUs.

- [ ] **Step 1: Update GPU fallback chain and comment**

In `saas/gpu/runpod_provider.py`, update lines 38-40:

From:
```python
        # GPU types to try in order of preference
        # Only GPUs with >= 40GB VRAM (32B AWQ model needs ~18GB weights + KV cache)
        gpu_types = [config.gpu_type, "NVIDIA L40S", "NVIDIA A40", "NVIDIA RTX A6000"]
```

To:
```python
        # GPU types to try in order of preference
        # Qwen3-14B needs ~28GB VRAM (weights + KV cache), fits on 40GB+ GPUs
        # L40S (48GB) is the sweet spot for price/performance
        gpu_types = [config.gpu_type, "NVIDIA L40S", "NVIDIA A40", "NVIDIA RTX A6000", "NVIDIA A100 40GB"]
```

Note: A100 40GB is moved to the end of the chain as a last resort — it's more expensive than L40S but always available. L40S (48GB, $0.44/hr on RunPod) is preferred over A100 (40GB, $0.76/hr).

- [ ] **Step 2: Commit**

```bash
git add saas/gpu/runpod_provider.py
git commit -m "chore: update GPU fallback chain for Qwen3-14B VRAM requirements

Qwen3-14B needs ~28GB VRAM (vs ~18GB for quantized Qwen2.5-32B-AWQ).
L40S (48GB, $0.44/hr) is the preferred GPU for price/performance.
A100 40GB moved to fallback position (more expensive, always available).

Part of sneg55/SimSwarm#66"
```

---

### Task 5: Update Test Fixtures and Verify End-to-End Config Flow

**Files:**
- Modify: `tests/conftest.py` (if `seeded_routing` fixture references old model)
- Test: `tests/test_jobs.py` (verify job creation uses new routing)

- [ ] **Step 1: Check and update test fixture**

Search for `Qwen2.5` in test files:

```bash
grep -rn "Qwen2.5\|32B-Instruct" tests/
```

If the `seeded_routing` fixture in `tests/conftest.py` hardcodes `Qwen/Qwen2.5-32B-Instruct-AWQ`, update it to match the new routing:

```python
# In the seeded_routing fixture, update the model_routing rows:
ModelRouting(
    sim_tier="small",
    model_id="Qwen/Qwen3-14B",
    gpu_type="NVIDIA L40S",
    max_rounds=200,
    vllm_args="--max-model-len 32768",
),
# ... same for medium and large
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest -x -v
```

Expected: All tests pass. If any test asserts on the old model name or `--quantization awq`, update those assertions.

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: update fixtures and assertions for Qwen3-14B routing

Test fixtures now use Qwen3-14B model routing to match the migration.

Part of sneg55/SimSwarm#66"
```

---

### Task 6: Configure Thinking Mode Per Pipeline Stage

**Files:**
- Modify: `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py:46,122`
- Modify: `vendor/miroshark/backend/wonderwall/simulations/polymarket/prompts.py:38`
- Modify: `vendor/miroshark/backend/app/services/oasis_profile_llm.py:46`

Qwen3 supports `/think` (chain-of-thought reasoning) and `/no_think` (direct response) modes. The mode is controlled by prepending the tag to the first user message or system prompt.

**Strategy:**
- **Persona generation** → thinking ON (default — no tag needed). MiroShark's `LLMClient.chat()` already strips `<think>` blocks from responses (line 127 of `llm_client.py`), so JSON parsing works.
- **Simulation agents** → thinking OFF (`/no_think` in system prompt). Avoids latency and prevents thinking tokens from interfering with tool/function calling.
- **Report generation** → thinking ON (default). `LLMClient.chat()` strips `<think>` blocks.

- [ ] **Step 1: Add `/no_think` to Twitter agent system prompt**

In `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py`, update `TwitterPromptBuilder.build_system_prompt()`. The return string currently starts with:

```python
        return f"""\
# WHO YOU ARE
```

Prepend `/no_think`:

```python
        return f"""\
/no_think
# WHO YOU ARE
```

- [ ] **Step 2: Add `/no_think` to Reddit agent system prompt**

Same file, `RedditPromptBuilder.build_system_prompt()`. The return string currently starts with:

```python
        return f"""\
# WHO YOU ARE
```

Prepend `/no_think`:

```python
        return f"""\
/no_think
# WHO YOU ARE
```

- [ ] **Step 3: Add `/no_think` to Polymarket trader system prompt**

In `vendor/miroshark/backend/wonderwall/simulations/polymarket/prompts.py`, update `PolymarketPromptBuilder.build_system_prompt()`. The return string currently starts with:

```python
        return f"""\
# WHO YOU ARE
```

Prepend `/no_think`:

```python
        return f"""\
/no_think
# WHO YOU ARE
```

- [ ] **Step 4: Increase max_tokens for persona generation**

Thinking tokens count toward the token budget. Persona generation currently uses `max_tokens=4096` (the default in `LLMClient.chat()`). With thinking mode, the model may use ~500-1000 tokens for reasoning before producing the JSON output. Increase the limit for persona calls.

In `vendor/miroshark/backend/app/services/oasis_profile_llm.py`, update the `llm.chat()` call (around line 46):

From:
```python
            content = llm.chat(
                messages=messages,
                temperature=0.7 - (attempt * 0.1),
                response_format={"type": "json_object"},
            )
```

To:
```python
            content = llm.chat(
                messages=messages,
                temperature=0.7 - (attempt * 0.1),
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
```

8192 tokens gives ~4K for thinking + ~4K for the persona JSON output.

- [ ] **Step 5: Verify `/no_think` is backward-compatible**

The `/no_think` tag is Qwen3-specific. On Qwen2.5 (or any non-Qwen3 model), it would appear as literal text in the system prompt. This is harmless — the model treats it as unknown text and ignores it. If you want strict backward compatibility, you can wrap the tag in a conditional, but it's not necessary for this migration.

- [ ] **Step 6: Commit**

```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/vendor/miroshark
git add backend/wonderwall/simulations/social_media/prompts.py \
       backend/wonderwall/simulations/polymarket/prompts.py \
       backend/app/services/oasis_profile_llm.py
git commit -m "feat: configure Qwen3 thinking mode per pipeline stage

- Simulation agents (Twitter, Reddit, Polymarket): /no_think disabled
  to avoid latency and tool-calling interference
- Persona generation: thinking ON (default), max_tokens increased to
  8192 to accommodate reasoning tokens + JSON output
- Report generation: thinking ON (default), <think> blocks already
  stripped by LLMClient

Part of sneg55/SimSwarm#66"
```

Then update submodule pointer in parent repo:

```bash
cd /Users/sneg55/Documents/GitHub/fishandcat
git add vendor/miroshark
git commit -m "chore: update miroshark submodule for thinking mode config"
```

---

### Task 7: Pre-load Model on RunPod Network Volumes (Operational)

This is an operational task, not a code change. Pre-loading the model weights on network volumes avoids a ~10 minute download on first pod startup.

- [ ] **Step 1: Download Qwen3-14B to US-TX-3 volume**

Create a temporary RunPod pod attached to volume `19hqjpxbp2` (US-TX-3) and download the model:

```bash
# On the pod:
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3-14B', cache_dir='/models/huggingface')
print('Download complete')
"
```

Verify the model is cached: `ls /models/huggingface/models--Qwen--Qwen3-14B/`

- [ ] **Step 2: Repeat for EU-RO-1 volume**

Same process for volume `8aplig09qc` (EU-RO-1).

- [ ] **Step 3: Verify vLLM can serve the model**

On the pod, test vLLM startup:

```bash
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model Qwen/Qwen3-14B \
    --download-dir /models/huggingface \
    --max-model-len 32768
```

Wait for "Application startup complete" in the logs. Then test:

```bash
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-14B","messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'
```

Expected: Model responds correctly.

- [ ] **Step 4: Terminate temp pods**

Clean up the temporary pods after verification.

---

### Task 8: Deploy and Validate on Production

- [ ] **Step 1: Build and push new worker image**

Push the Dockerfile changes to main. CI/CD builds the new worker image with vLLM v0.8.5.

```bash
git push origin main
```

Wait for the "Build Worker Image" GitHub Action to complete. Note the new image tag.

- [ ] **Step 2: Update worker image tag**

Update `saas/jobs/config.py:10` with the new image tag:

```python
WORKER_IMAGE_DEFAULT_TAG = "v20260406XXXXXX"  # replace with actual CI tag
```

Commit and push.

- [ ] **Step 3: Run alembic migration on production**

The CI deploy runs alembic automatically. Verify the model_routing table was updated:

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose exec -T app python3 -c \"
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg', ''))
with e.connect() as c:
    for r in c.execute(text('SELECT sim_tier, model_id, gpu_type FROM model_routing')):
        print(r)
\""
```

Expected: All tiers show `Qwen/Qwen3-14B` on `NVIDIA L40S`.

- [ ] **Step 4: Run a test simulation**

Create a small sim for the test account and verify it completes:

```bash
TOKEN=$(curl -s -X POST https://simswarm.xyz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nsawinyh@gmail.com","password":"..."}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST https://simswarm.xyz/api/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_text": "Test: Qwen3 migration validation",
    "goal": "Verify simulation pipeline works with Qwen3-14B",
    "tier": "small",
    "enrich_web": false
  }'
```

Monitor until COMPLETED. Check:
- Personas have structured SOUL/STYLE/BEHAVIOR sections
- Report is coherent
- Agent engagement is non-zero (likes, comments)
- GPU cost is lower than previous runs (should be ~$0.44/hr vs ~$0.76/hr)

---

## Summary of Changes

| Change | Impact | Risk |
|--------|--------|------|
| vLLM upgrade v0.6.6 → v0.8.5 | Required for Qwen3 support | Medium — may break pip dependencies; verified by Docker build |
| Model routing → Qwen3-14B | All new sims use Qwen3 | Low — DB-driven, instant rollback via downgrade migration |
| GPU → L40S preferred | ~42% cost reduction ($0.44 vs $0.76/hr) | Low — fallback chain includes A100/A40 |
| Thinking mode per stage | Persona/report get chain-of-thought; agents stay fast | Low — `/no_think` is harmless on non-Qwen3 models |
| Default fallbacks updated | Cosmetic — only used when env vars missing | Very low |
| Network volume pre-load | Faster cold starts | None — optional optimization |

## Rollback Plan

If Qwen3-14B produces poor quality:
```bash
# Revert the alembic migration (restores Qwen2.5-32B-Instruct-AWQ routing)
cd /opt/fishcloud
docker compose exec app alembic downgrade -1
```

In-flight jobs won't be affected (they use the model that was loaded when the pod started). New jobs will immediately use the reverted model.

---

## Phase 3 Design Sketch: Multi-Model Pipeline

After Phase 2 validates Qwen3 works, Phase 3 optimizes by using different models for different pipeline stages:

| Stage | Model | Mode | Rationale |
|-------|-------|------|-----------|
| Graph + Persona | Qwen3-32B | `/think` | One-time batch, quality matters |
| Simulation | Qwen3-30B-A3B (MoE) | `/no_think` | 3B activated params, ~10x faster |
| Report | Qwen3-32B | `/think` | Chain-of-thought improves synthesis |

**Architecture approach:**

1. **Extend ModelRouting** — Add `sim_model_id` and `sim_vllm_args` columns for the simulation-phase model. Keep `model_id` as the "smart" model for graph/persona/report.

2. **Pass both models to worker** — `JobConfig.to_worker_env()` adds `SIM_MODEL_ID` and `SIM_VLLM_ARGS` env vars alongside the existing `MODEL_ID`.

3. **Model swap in run_job.py** — Between pipeline phases, call a helper that:
   - Kills the current vLLM process
   - Relaunches with the sim model
   - Waits for health check
   - After simulation, swaps back to the smart model for report generation

4. **Wire SMART_MODEL config** — The existing `SMART_MODEL_NAME` / `create_smart_llm_client()` pattern in MiroShark already supports two-tier routing. `service_init.py` just needs to set `SMART_MODEL_NAME` from the env var. Report generation (`report_agent.py`) and ontology extraction (`ontology_generator.py`) already use `create_smart_llm_client()`.

5. **Thinking mode** — Already implemented in Phase 2. Agent prompts have `/no_think`, batch operations use thinking by default.

This requires:
- 1 alembic migration (add columns)
- `saas/jobs/config.py` changes (new env vars)
- `infra/docker/run_job.py` model-swap helper
- `infra/docker/service_init.py` SMART_MODEL wiring
- Network volume pre-loading of both models (~48GB total: 32B dense + 30B MoE)
- GPU must have enough VRAM for the larger model (Qwen3-32B needs ~64GB → H100-80GB)

This will be planned as a separate document after Phase 2 is deployed and validated.
