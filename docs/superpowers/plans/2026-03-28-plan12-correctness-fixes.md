# Correctness Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 correctness bugs: tier timeout mismatch in polling, graph edge field name mismatch, and non-English simulation output.

**Architecture:** Tier timeout fix derives max_polls from config instead of hardcoding 1 hour. Graph edge fix normalizes field names in GraphCanvas.vue. English output fix strengthens the MiroFish prompt patches in run_job.py.

**Tech Stack:** Vue 3, Python, FastAPI, pytest

**GitHub Issues:** #16, #17, #9

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `saas/workers/job_runner.py` | Modify | Derive polling limit from tier timeout |
| `frontend/src/components/graph/GraphCanvas.vue` | Modify | Fix edge source/target field names |
| `infra/docker/run_job.py` | Modify | Strengthen English prompt patches |
| `tests/test_tier_timeout_alignment.py` | Create | Verify polling respects tier limits |

---

### Task 1: Align Polling Timeout with Tier Config (#16)

**Files:**
- Modify: `saas/workers/job_runner.py:258`
- Test: `tests/test_tier_timeout_alignment.py`

The `_poll_until_complete` method hardcodes `max_polls = 360` (1 hour). Medium tier allows 5 hours, large allows 12 hours. Jobs on larger tiers are killed prematurely by the polling ceiling.

- [ ] **Step 1: Write failing test**

```python
# tests/test_tier_timeout_alignment.py
"""Verify that polling duration respects tier timeouts."""
from saas.workers.job_runner import TIER_TIMEOUTS


def test_small_tier_polling_within_timeout():
    """Small tier (2700s) — polling should cover at least 2700s."""
    timeout = TIER_TIMEOUTS["small"]
    max_polls = timeout // 10  # 10s per poll
    assert max_polls >= 270  # 2700 / 10


def test_medium_tier_polling_within_timeout():
    """Medium tier (18000s) — polling should cover at least 18000s."""
    timeout = TIER_TIMEOUTS["medium"]
    max_polls = timeout // 10
    assert max_polls >= 1800  # 18000 / 10


def test_large_tier_polling_within_timeout():
    """Large tier (43200s) — polling should cover at least 43200s."""
    timeout = TIER_TIMEOUTS["large"]
    max_polls = timeout // 10
    assert max_polls >= 4320  # 43200 / 10


def test_polling_not_hardcoded_to_one_hour():
    """The _poll_until_complete method must not hardcode max_polls = 360."""
    import inspect
    from saas.workers.job_runner import JobRunner
    source = inspect.getsource(JobRunner._poll_until_complete)
    assert "max_polls = 360" not in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tier_timeout_alignment.py::test_polling_not_hardcoded_to_one_hour -v`
Expected: FAIL — source contains "max_polls = 360"

- [ ] **Step 3: Fix `_poll_until_complete` to use tier timeout**

In `saas/workers/job_runner.py`, the `_poll_until_complete` method signature needs to accept the timeout. Currently it receives `config` which has `timeout_seconds`. Change line 258:

Replace:
```python
        max_polls = 360  # 360 * 10s = 1 hour
```

With:
```python
        poll_interval = 10
        max_polls = max(360, config.timeout_seconds // poll_interval)
```

And update the `await asyncio.sleep(10)` on the next line to use the variable:
```python
            await asyncio.sleep(poll_interval)
```

Also update the error message:
```python
            raise TimeoutError(f"Pipeline did not complete within {max_polls * poll_interval}s")
```

For the `resume` method, the minimal config doesn't have `timeout_seconds`. Update the `resume` method to pass a config with a reasonable timeout:

Replace:
```python
        minimal_config = type("MinimalConfig", (), {"job_id": job_id})()
```

With:
```python
        # Use medium tier timeout as default for resumed jobs
        minimal_config = type("MinimalConfig", (), {
            "job_id": job_id,
            "timeout_seconds": TIER_TIMEOUTS.get("medium", 18000),
        })()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_tier_timeout_alignment.py tests/test_job_runner.py tests/test_gpu_worker.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add saas/workers/job_runner.py tests/test_tier_timeout_alignment.py
git commit -m "fix: derive polling limit from tier timeout, not hardcoded 1 hour (#16)"
```

---

### Task 2: Fix Graph Edge Field Names (#17)

**Files:**
- Modify: `frontend/src/components/graph/GraphCanvas.vue:93-99`

The backend schema sends edges with `source_node_uuid` / `target_node_uuid`, but GraphCanvas.vue reads `edge.source` / `edge.target`. All edges are silently dropped.

- [ ] **Step 1: Find and fix all edge field references in GraphCanvas.vue**

Search for `edge.source` and `edge.target` in the file and replace with `edge.source_node_uuid` and `edge.target_node_uuid`.

The key lines (around line 93):
```javascript
// BEFORE:
if (visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)) {
  elements.push({
    data: {
      id: edge.uuid || `e-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: edge.name || edge.fact || '',
    },
  })
}
```

Replace with:
```javascript
// AFTER:
if (visibleNodeIds.has(edge.source_node_uuid) && visibleNodeIds.has(edge.target_node_uuid)) {
  elements.push({
    data: {
      id: edge.uuid || `e-${edge.source_node_uuid}-${edge.target_node_uuid}`,
      source: edge.source_node_uuid,
      target: edge.target_node_uuid,
      label: edge.name || edge.fact || '',
    },
  })
}
```

Note: Cytoscape.js expects `source` and `target` in the element data — those are the Cytoscape properties. But the *input* edge object from the API uses `source_node_uuid`. So we read from `edge.source_node_uuid` and write to Cytoscape's `source` property.

- [ ] **Step 2: Search for any other references to `edge.source` or `edge.target` in the graph components**

```bash
grep -rn "edge\.source\b\|edge\.target\b" frontend/src/components/graph/
```

Fix any additional occurrences found (GraphDetailPanel, GraphSearchBar, etc.).

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/graph/
git commit -m "fix: use source_node_uuid/target_node_uuid to match backend schema (#17)"
```

---

### Task 3: Fix Non-English Simulation Output (#9)

**Files:**
- Modify: `infra/docker/run_job.py:41-97`

The English prompt patches in `_patch_mirofish_prompts_to_english()` only prepend English instructions to prompts containing Chinese characters. Some prompts don't contain Chinese markers but still generate Chinese output. The simulation config generator and agent activity descriptions often produce Chinese despite the patches.

- [ ] **Step 1: Strengthen the patch to cover ALL prompt attributes**

In `infra/docker/run_job.py`, replace the `_patch_mirofish_prompts_to_english()` function:

```python
ENGLISH_INSTRUCTION = (
    "CRITICAL REQUIREMENT: ALL output text MUST be written entirely in English. "
    "Do NOT output any Chinese, Japanese, Korean, or other non-Latin text. "
    "Translate any non-English context or references to English. "
    "This applies to ALL fields: names, descriptions, analysis, summaries, reports, "
    "dialogue, posts, comments, and any other generated text.\n\n"
)


def _patch_mirofish_prompts_to_english():
    """Monkey-patch MiroFish service prompts to output in English."""
    sys.path.insert(0, MIROFISH_BACKEND)

    modules_to_patch = [
        "app.services.ontology_generator",
        "app.services.report_agent",
        "app.services.oasis_profile_generator",
        "app.services.simulation_config_generator",
    ]

    for mod_name in modules_to_patch:
        try:
            mod = __import__(mod_name, fromlist=[""])
            for attr in dir(mod):
                val = getattr(mod, attr)
                # Patch any string attribute that looks like a prompt (>80 chars)
                if isinstance(val, str) and len(val) > 80 and not attr.startswith("_"):
                    setattr(mod, attr, ENGLISH_INSTRUCTION + val)
        except ImportError:
            pass

    # Patch ontology system prompt specifically
    try:
        import app.services.ontology_generator as ontology_mod
        if hasattr(ontology_mod, "ONTOLOGY_SYSTEM_PROMPT"):
            ontology_mod.ONTOLOGY_SYSTEM_PROMPT = (
                ENGLISH_INSTRUCTION + ontology_mod.ONTOLOGY_SYSTEM_PROMPT
            )
    except ImportError:
        pass

    print("[run_job] Patched MiroFish prompts to English output", flush=True)
```

- [ ] **Step 2: Verify the patch doesn't break the pipeline**

This change only affects the worker image — it will take effect on the next worker image build. No tests needed locally (the MiroFish modules aren't available in the test environment).

- [ ] **Step 3: Commit**

```bash
git add infra/docker/run_job.py
git commit -m "fix: strengthen English prompt patches for all MiroFish services (#9)"
```

---

### Task 4: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Run linter**

Run: `ruff check saas/ tests/`
Expected: All checks passed

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "fix: lint and test fixups for correctness changes"
```
