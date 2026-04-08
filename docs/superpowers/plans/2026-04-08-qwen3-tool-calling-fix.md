# Qwen3 Tool Calling Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 99.7% tool-call failure rate by enabling vLLM's native tool-call parser for Qwen3-14B and adding resilience for empty tool-call responses.

**Architecture:** vLLM requires `--enable-auto-tool-choice --tool-call-parser hermes` flags to parse Qwen3's Hermes-format `<tool_call>` XML tags into OpenAI-compatible `tool_calls` response fields. Without these, CAMEL's `response.info['tool_calls']` is always empty. Secondary fix adds a do_nothing fallback so empty tool-call lists are logged and traced instead of silently dropped.

**Tech Stack:** vLLM 0.8.5, CAMEL-AI 0.2.78, Alembic, PostgreSQL, FastAPI

---

### Task 1: Add vLLM tool-calling flags to Alembic migration

**Files:**
- Create: `alembic/versions/s0t1u2v3w4x5_enable_vllm_tool_calling.py`

The `model_routing` table stores `vllm_args` per tier. This migration updates all tiers from `--max-model-len 32768` to include the tool-calling flags.

- [ ] **Step 1: Create migration file**

```python
"""enable vLLM tool-call parser for Qwen3

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-04-08
"""
from alembic import op

revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None

NEW_VLLM_ARGS = "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes"
OLD_VLLM_ARGS = "--max-model-len 32768"


def upgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET vllm_args = '{NEW_VLLM_ARGS}'
        WHERE vllm_args = '{OLD_VLLM_ARGS}';
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET vllm_args = '{OLD_VLLM_ARGS}'
        WHERE vllm_args = '{NEW_VLLM_ARGS}';
    """)
```

- [ ] **Step 2: Verify migration chain**

Run: `alembic heads`
Expected: `s0t1u2v3w4x5 (head)`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/s0t1u2v3w4x5_enable_vllm_tool_calling.py
git commit -m "feat: enable vLLM tool-call parser for Qwen3 (hermes format)"
```

---

### Task 2: Update default vLLM args in start.sh and config.py

**Files:**
- Modify: `infra/docker/start.sh:17`
- Modify: `saas/jobs/config.py:61`

Update fallback defaults so new deployments and null DB values also get tool-calling flags.

- [ ] **Step 1: Update start.sh default**

In `infra/docker/start.sh`, change line 17 from:
```bash
    ${VLLM_ARGS:---max-model-len 32768} \
```
to:
```bash
    ${VLLM_ARGS:---max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes} \
```

- [ ] **Step 2: Update config.py fallback**

In `saas/jobs/config.py`, change the `to_worker_env` fallback (line 61) from:
```python
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768",
```
to:
```python
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes",
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker/start.sh saas/jobs/config.py
git commit -m "feat: default vLLM args include tool-call-parser hermes"
```

---

### Task 3: Handle empty tool_calls with do_nothing fallback

**Files:**
- Modify: `vendor/miroshark/backend/wonderwall/social_agent/agent.py:161-189`

When vLLM returns no tool calls (e.g. model produces plain text), log a warning and execute `do_nothing` so the round is traced.

- [ ] **Step 1: Update perform_action_by_llm**

Replace lines 161-189 with:

```python
    async def perform_action_by_llm(self):
        # Get environment observation:
        env_prompt = await self.env.to_text_prompt()
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=(
                f"Please perform actions after observing the "
                f"platform environment. Use the available tools to take "
                f"action. Don't limit yourself to just one type of action. "
                f"Here is your current environment: {env_prompt}"))
        try:
            agent_log.info(
                f"Agent {self.social_agent_id} observing environment: "
                f"{env_prompt}")
            response = await self.astep(user_msg)
            if not response.info.get('tool_calls'):
                agent_log.warning(
                    f"Agent {self.social_agent_id} returned no tool calls, "
                    f"falling back to do_nothing")
                await self.env.action.do_nothing()
                return response
            for tool_call in response.info['tool_calls']:
                action_name = tool_call.tool_name
                args = tool_call.args
                agent_log.info(f"Agent {self.social_agent_id} performed "
                               f"action: {action_name} with args: {args}")
                if action_name not in ALL_SOCIAL_ACTIONS:
                    agent_log.info(
                        f"Agent {self.social_agent_id} get the result: "
                        f"{tool_call.result}")

                return response
        except Exception as e:
            agent_log.error(f"Agent {self.social_agent_id} error: {e}")
            return e
```

- [ ] **Step 2: Commit**

```bash
git add vendor/miroshark/backend/wonderwall/social_agent/agent.py
git commit -m "fix: handle empty tool_calls with do_nothing fallback + warning log"
```

---

### Task 4: Deploy and validate

- [ ] **Step 1: Run alembic migration on production**

```bash
ssh simswarm "cd /opt/fishcloud && docker compose exec app alembic upgrade head"
```

- [ ] **Step 2: Rebuild and push worker image**

```bash
docker build -f infra/docker/Dockerfile.worker -t ghcr.io/sneg55/simswarm-worker:v20260408-toolfix .
docker push ghcr.io/sneg55/simswarm-worker:v20260408-toolfix
```

- [ ] **Step 3: Update WORKER_IMAGE_DEFAULT_TAG in config.py**

Change `saas/jobs/config.py:10`:
```python
WORKER_IMAGE_DEFAULT_TAG = "v20260408-toolfix"
```

- [ ] **Step 4: Deploy via CI**

Push to main, let GitHub Actions deploy.

- [ ] **Step 5: Run a small-tier test simulation via the web UI**

Use agent-browser to launch a simulation and verify tool calls are being made.
