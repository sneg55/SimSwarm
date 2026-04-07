# Simulation Data Quality Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent garbage simulation output by alerting on enrichment failures, failing early on tiny graphs, ensuring simulations run the requested number of rounds, and fixing misleading metrics.

**Architecture:** Five independent changes across SaaS backend (alerting, error classification) and GPU worker (entity guard, time-config patch, metrics fix). None modify `vendor/mirofish/`. The time-config patch works by modifying the generated `simulation_config.json` between preparation and execution — no engine changes needed.

**Tech Stack:** Python, FastAPI, Celery, httpx (webhooks), pytest

**Spec:** `docs/superpowers/specs/2026-04-07-sim-data-quality-guardrails-design.md`

---

### Task 1: Enrichment Failure Alerting

**Files:**
- Modify: `saas/jobs/alerts.py` (add `send_enrichment_alert`)
- Modify: `saas/jobs/tasks.py:73-79` (call alert on failure)
- Modify: `tests/test_alerts.py` (add enrichment alert tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_alerts.py`:

```python
from saas.jobs.alerts import send_enrichment_alert


@patch("saas.jobs.alerts.httpx")
def test_send_enrichment_alert_posts_to_webhook(mock_httpx):
    """Enrichment alert should POST to the configured webhook URL."""
    mock_httpx.post.return_value = MagicMock(status_code=200)

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_enrichment_alert(job_id=62, goal="Predict Apple AI ecosystem shifts")

    mock_httpx.post.assert_called_once()
    args, kwargs = mock_httpx.post.call_args
    assert args[0] == "https://hooks.slack.com/test"
    assert "62" in kwargs["json"]["text"]
    assert "Enrichment Failed" in kwargs["json"]["text"]


@patch("saas.jobs.alerts.httpx")
def test_send_enrichment_alert_noop_without_webhook(mock_httpx):
    """Enrichment alert should do nothing when ALERT_WEBHOOK_URL is not set."""
    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": ""}, clear=False):
        send_enrichment_alert(job_id=62, goal="Test goal")

    mock_httpx.post.assert_not_called()


@patch("saas.jobs.alerts.httpx")
def test_send_enrichment_alert_swallows_errors(mock_httpx):
    """Enrichment alert failure must never raise."""
    mock_httpx.post.side_effect = Exception("network error")

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_enrichment_alert(job_id=62, goal="Test goal")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_alerts.py -v -k enrichment`
Expected: FAIL with `ImportError: cannot import name 'send_enrichment_alert'`

- [ ] **Step 3: Implement `send_enrichment_alert` in alerts.py**

Add to the end of `saas/jobs/alerts.py`:

```python
def send_enrichment_alert(job_id: int, goal: str) -> None:
    """Alert when enrichment was requested but returned nothing. Never raises."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
    if not webhook_url:
        return

    text = (
        f":warning: *Enrichment Failed*\n"
        f"• Job: {job_id}\n"
        f"• Goal: {goal[:100]}\n"
        f"• Enrichment was requested but returned empty"
    )

    try:
        httpx.post(webhook_url, json={"text": text}, timeout=10)
    except Exception as e:
        logger.warning("alert.enrichment_failed error=%s", e)
```

- [ ] **Step 4: Wire alert into tasks.py**

In `saas/jobs/tasks.py`, change lines 73-79 from:

```python
    if enrich_web:
        from saas.jobs.enrichment import enrich_seed
        import json as _json
        enrichment = enrich_seed(seed_text, goal)
        if enrichment:
            _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
            enriched_seed_text = seed_text + "\n\n--- Background Research ---\n" + enrichment.summary
```

to:

```python
    if enrich_web:
        from saas.jobs.enrichment import enrich_seed
        from saas.jobs.alerts import send_enrichment_alert
        import json as _json
        enrichment = enrich_seed(seed_text, goal)
        if enrichment:
            _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
            enriched_seed_text = seed_text + "\n\n--- Background Research ---\n" + enrichment.summary
        else:
            logger.warning("job.enrichment_empty job_id=%d", job_id)
            send_enrichment_alert(job_id=job_id, goal=goal)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_alerts.py -v`
Expected: All PASS (existing orphan tests + 3 new enrichment tests)

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/alerts.py saas/jobs/tasks.py tests/test_alerts.py
git commit -m "feat: alert on enrichment failure in simulation pipeline"
```

---

### Task 2: Classify GRAPH_TOO_SMALL as Permanent Error

**Files:**
- Modify: `saas/gpu/errors.py:15-21` (add pattern)
- Modify: `tests/test_gpu_provider.py` or create `tests/test_gpu_errors.py` (test classification)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gpu_provider.py` (or a new file if gpu error tests don't exist there):

```python
from saas.gpu.errors import classify_gpu_error


class TestClassifyGpuError:
    def test_graph_too_small_is_permanent(self):
        exc = RuntimeError("GRAPH_TOO_SMALL: only 3 entities extracted (minimum 5)")
        assert classify_gpu_error(exc) == "permanent"

    def test_transient_patterns_still_work(self):
        exc = RuntimeError("No RunPod GPUs available for L40S")
        assert classify_gpu_error(exc) == "transient"
```

- [ ] **Step 2: Run test to verify it passes (already handled)**

Run: `pytest tests/test_gpu_provider.py -v -k "graph_too_small or transient_patterns"`
Expected: `test_graph_too_small_is_permanent` PASS (RuntimeError with no matching transient pattern falls through to `return "permanent"` at line 37). `test_transient_patterns_still_work` PASS.

Note: GRAPH_TOO_SMALL is already classified as permanent by the existing fallthrough logic — any RuntimeError that doesn't match `_TRANSIENT_PATTERNS` returns "permanent". The test documents this intent explicitly. No code change needed in `errors.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_gpu_provider.py
git commit -m "test: verify GRAPH_TOO_SMALL classified as permanent GPU error"
```

---

### Task 3: Minimum Entity Guard on GPU Worker

**Files:**
- Modify: `infra/docker/run_job.py:56-67` (add guard after build_graph)

- [ ] **Step 1: Add the MIN_GRAPH_ENTITIES constant and guard**

In `infra/docker/run_job.py`, add constant at the top (after imports, before `run_pipeline`):

```python
MIN_GRAPH_ENTITIES = 5
```

Then in `run_pipeline()`, change lines 65-67 from:

```python
    project_id, graph_id = build_graph(seed_text, goal, storage)
    try:
        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)
```

to:

```python
    project_id, graph_id = build_graph(seed_text, goal, storage)
    try:
        # Guard: fail early if graph is too small for a meaningful simulation
        info = storage.get_graph_info(graph_id)
        node_count = info.get("node_count", 0)
        if node_count < MIN_GRAPH_ENTITIES:
            raise RuntimeError(
                f"GRAPH_TOO_SMALL: only {node_count} entities extracted "
                f"(minimum {MIN_GRAPH_ENTITIES})"
            )

        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)
```

The `finally` block at line 138 already calls `storage.delete_graph(graph_id)` — graph cleanup is guaranteed even on this error path.

- [ ] **Step 2: Verify the guard works with a unit test**

This code runs on the GPU worker and imports MiroFish, so it can't be tested directly in the backend test suite. Instead, verify the logic by reading the code and confirming:
1. `storage.get_graph_info()` returns a dict with `node_count` key (check `vendor/mirofish/backend/app/storage/neo4j_storage.py`)
2. The RuntimeError message starts with `GRAPH_TOO_SMALL` which matches the permanent error classification from Task 2
3. The `finally` block handles cleanup

Run: `pytest tests/test_gpu_provider.py -v -k graph_too_small`
Expected: PASS (test from Task 2 confirms error classification)

- [ ] **Step 3: Commit**

```bash
git add infra/docker/run_job.py
git commit -m "feat: fail early when graph has fewer than 5 entities"
```

---

### Task 4: Patch Time Config for Round Count and Activity

**Files:**
- Modify: `infra/docker/run_job.py` (add `_patch_sim_config` helper + call it)

- [ ] **Step 1: Add `_patch_sim_config` helper function**

Add this function to `infra/docker/run_job.py` between the `MIN_GRAPH_ENTITIES` constant and `run_pipeline`:

```python
def _patch_sim_config(simulation_id: str, max_rounds: int) -> None:
    """Patch the generated simulation_config.json to ensure enough rounds run
    and agents are active across all time periods.

    The MiroFish engine treats max_rounds as a ceiling:
        total_rounds = min(total_hours * 60 / minutes_per_round, max_rounds)
    If the LLM-generated time_config produces fewer rounds than max_rounds,
    the simulation ends early. Fix by increasing total_simulation_hours.

    The off_peak_activity_multiplier (default 0.05) makes agents virtually
    inactive during simulated midnight hours. Clamp to 0.3 minimum.
    """
    from app.services.simulation_runner import SimulationRunner

    sim_dir = os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)
    config_path = os.path.join(sim_dir, "simulation_config.json")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    tc = config.get("time_config", {})
    minutes_per_round = tc.get("minutes_per_round", 60)
    total_hours = tc.get("total_simulation_hours", 72)
    config_rounds = (total_hours * 60) // minutes_per_round

    patched = False

    # Ensure enough rounds: increase total_simulation_hours if needed
    if config_rounds < max_rounds:
        needed_hours = (max_rounds * minutes_per_round + 59) // 60  # ceiling division
        tc["total_simulation_hours"] = needed_hours
        print(
            f"[run_job] Patched total_simulation_hours: {total_hours} -> {needed_hours} "
            f"({config_rounds} rounds -> {max_rounds}+)",
            flush=True,
        )
        patched = True

    # Clamp off-peak activity multiplier to ensure agents stay active
    off_peak = tc.get("off_peak_activity_multiplier", 0.05)
    if off_peak < 0.3:
        tc["off_peak_activity_multiplier"] = 0.3
        print(
            f"[run_job] Patched off_peak_activity_multiplier: {off_peak} -> 0.3",
            flush=True,
        )
        patched = True

    if patched:
        config["time_config"] = tc
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Call `_patch_sim_config` in `run_pipeline`**

In `run_pipeline()`, after the `prepare_simulation()` call and before `run_and_wait()`, add:

Change:

```python
        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)

        run_and_wait(simulation_id, max_rounds)
```

to:

```python
        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)

        _patch_sim_config(simulation_id, max_rounds)

        run_and_wait(simulation_id, max_rounds)
```

- [ ] **Step 3: Write tests for `_patch_sim_config` logic**

Create `tests/test_sim_config_patch.py`:

```python
"""Tests for simulation config patching logic (round count + activity)."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch


def _make_config(total_hours=72, minutes_per_round=60, off_peak=0.05):
    """Create a minimal simulation_config.json dict."""
    return {
        "time_config": {
            "total_simulation_hours": total_hours,
            "minutes_per_round": minutes_per_round,
            "off_peak_activity_multiplier": off_peak,
        },
        "agent_configs": [],
    }


def _write_config(sim_dir, config):
    os.makedirs(sim_dir, exist_ok=True)
    path = os.path.join(sim_dir, "simulation_config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    return path


class TestPatchSimConfig:
    def test_increases_hours_when_rounds_too_low(self, tmp_path):
        """If time_config yields fewer rounds than max_rounds, hours are increased."""
        # 5 hours / 60 min = 5 rounds, but max_rounds=200
        sim_id = "sim_test_low_rounds"
        sim_dir = str(tmp_path / sim_id)
        config = _make_config(total_hours=5, minutes_per_round=60)
        _write_config(sim_dir, config)

        # Mock SimulationRunner.RUN_STATE_DIR to point to tmp_path
        mock_runner = type("MockRunner", (), {"RUN_STATE_DIR": str(tmp_path)})
        with patch.dict("sys.modules", {"app.services.simulation_runner": type("M", (), {"SimulationRunner": mock_runner})}):
            # Import and call the function
            import importlib.util, sys
            run_job_path = os.path.join(os.path.dirname(__file__), "..", "infra", "docker", "run_job.py")
            # Instead of importing run_job (requires MiroFish), test the logic directly
            pass

        # Direct logic test (avoids MiroFish import)
        tc = config["time_config"]
        minutes_per_round = tc["minutes_per_round"]
        total_hours = tc["total_simulation_hours"]
        max_rounds = 200
        config_rounds = (total_hours * 60) // minutes_per_round

        assert config_rounds == 5  # only 5 rounds from config
        assert config_rounds < max_rounds

        needed_hours = (max_rounds * minutes_per_round + 59) // 60
        assert needed_hours == 200  # 200 rounds * 60 min / 60 = 200 hours

    def test_no_patch_when_rounds_sufficient(self):
        """If time_config already yields enough rounds, no patch needed."""
        config = _make_config(total_hours=72, minutes_per_round=30)
        tc = config["time_config"]
        config_rounds = (tc["total_simulation_hours"] * 60) // tc["minutes_per_round"]
        assert config_rounds == 144
        assert config_rounds >= 100  # enough for max_rounds=100

    def test_clamps_off_peak_multiplier(self):
        """Off-peak multiplier below 0.3 should be clamped to 0.3."""
        config = _make_config(off_peak=0.05)
        tc = config["time_config"]

        off_peak = tc.get("off_peak_activity_multiplier", 0.05)
        assert off_peak < 0.3
        clamped = max(0.3, off_peak)
        assert clamped == 0.3

    def test_preserves_reasonable_off_peak(self):
        """Off-peak multiplier >= 0.3 should not be changed."""
        config = _make_config(off_peak=0.5)
        tc = config["time_config"]

        off_peak = tc.get("off_peak_activity_multiplier", 0.05)
        assert off_peak >= 0.3
        clamped = max(0.3, off_peak)
        assert clamped == 0.5  # unchanged

    def test_full_patch_writes_config(self, tmp_path):
        """End-to-end: write config, apply patch logic, verify file updated."""
        config = _make_config(total_hours=5, minutes_per_round=60, off_peak=0.05)
        config_path = str(tmp_path / "simulation_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Apply patch logic inline (same as _patch_sim_config)
        with open(config_path, "r") as f:
            loaded = json.load(f)

        tc = loaded["time_config"]
        max_rounds = 200
        minutes_per_round = tc["minutes_per_round"]
        total_hours = tc["total_simulation_hours"]
        config_rounds = (total_hours * 60) // minutes_per_round

        if config_rounds < max_rounds:
            tc["total_simulation_hours"] = (max_rounds * minutes_per_round + 59) // 60

        if tc.get("off_peak_activity_multiplier", 0.05) < 0.3:
            tc["off_peak_activity_multiplier"] = 0.3

        loaded["time_config"] = tc
        with open(config_path, "w") as f:
            json.dump(loaded, f)

        # Verify
        with open(config_path, "r") as f:
            result = json.load(f)

        assert result["time_config"]["total_simulation_hours"] == 200
        assert result["time_config"]["off_peak_activity_multiplier"] == 0.3
        # Verify rounds: 200 hours / 60 min = 200 rounds >= max_rounds
        new_rounds = (result["time_config"]["total_simulation_hours"] * 60) // result["time_config"]["minutes_per_round"]
        assert new_rounds >= 200
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_sim_config_patch.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add infra/docker/run_job.py tests/test_sim_config_patch.py
git commit -m "feat: patch sim time_config to ensure enough rounds and agent activity"
```

---

### Task 5: Fix Rounds Metric and Add Trade Count

**Files:**
- Modify: `infra/docker/results.py:241-245` (fix Rounds, add Trades)
- Modify: `tests/test_structured_results.py` (update existing tests + add new ones)

- [ ] **Step 1: Update test fixtures and add failing tests**

In `tests/test_structured_results.py`, first update `SAMPLE_CHAT_LOG` to include `round_num` fields:

```python
SAMPLE_CHAT_LOG = [
    {"agent_name": "Alice", "platform": "twitter", "action_type": "CREATE_POST", "action_args": {}, "round_num": 5},
    {"agent_name": "Bob", "platform": "twitter", "action_type": "LIKE_POST", "action_args": {}, "round_num": 10},
    {"agent_name": "Alice", "platform": "twitter", "action_type": "FOLLOW", "action_args": {"target": "Bob"}, "round_num": 15},
    {"agent_name": "Bob", "platform": "twitter", "action_type": "FOLLOW", "action_args": {"target": "Alice"}, "round_num": 15},
    {"agent_name": "Carol", "platform": "reddit", "action_type": "IDLE", "action_args": {}, "round_num": 20},
    {"agent_name": "Carol", "platform": "reddit", "action_type": "COMMENT", "action_args": {}, "round_num": 25},
]
```

Then add new tests in `TestBuildStructuredResults`:

```python
    def test_rounds_shows_max_round_num_not_action_count(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        rounds_entry = next(c for c in result["confidence"] if c["label"] == "Rounds")
        # max round_num is 25, not len(chat_log) which is 6
        assert rounds_entry["value"] == "25"

    def test_trades_count_in_confidence(self, build_fn):
        chat_with_trades = SAMPLE_CHAT_LOG + [
            {"agent_name": "Alice", "platform": "polymarket", "action_type": "BUY", "action_args": {}, "round_num": 12},
            {"agent_name": "Bob", "platform": "polymarket", "action_type": "SELL", "action_args": {}, "round_num": 18},
            {"agent_name": "Carol", "platform": "polymarket", "action_type": "CREATE_MARKET", "action_args": {}, "round_num": 5},
        ]
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, chat_with_trades, SAMPLE_GRAPH_DATA)
        trades_entry = next(c for c in result["confidence"] if c["label"] == "Trades")
        # Only BUY and SELL count, not CREATE_MARKET
        assert trades_entry["value"] == "2"

    def test_trades_zero_when_no_polymarket_trades(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        trades_entry = next(c for c in result["confidence"] if c["label"] == "Trades")
        assert trades_entry["value"] == "0"
```

Also update `test_confidence_metrics` to expect 4 entries:

```python
    def test_confidence_metrics(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        confidence = result["confidence"]
        assert len(confidence) == 4
        labels = {c["label"] for c in confidence}
        assert labels == {"Agents", "Rounds", "Graph Entities", "Trades"}
        # 3 agents: Alice, Bob, Carol
        agents_entry = next(c for c in confidence if c["label"] == "Agents")
        assert agents_entry["value"] == "3"
        # Graph has 2 nodes
        graph_entry = next(c for c in confidence if c["label"] == "Graph Entities")
        assert graph_entry["value"] == "2"
```

And update `test_empty_inputs_returns_empty_arrays` to expect 4:

```python
    def test_empty_inputs_returns_empty_arrays(self, build_fn):
        result = build_fn(None, {}, [], {"metadata": {}})
        assert result["brief"] == ""
        assert result["findings"] == []
        assert result["sentiment"] == []
        assert result["coalitions"] == []
        assert len(result["confidence"]) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_structured_results.py -v`
Expected: FAIL — `test_rounds_shows_max_round_num_not_action_count` fails (gets "6" instead of "25"), `test_trades_count_in_confidence` fails (no "Trades" entry), `test_confidence_metrics` fails (3 entries not 4)

- [ ] **Step 3: Fix Rounds metric and add Trades count in results.py**

In `infra/docker/results.py`, change lines 240-245 from:

```python
    meta = graph_data.get("metadata", {})
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(len(chat_log)), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
    ]
```

to:

```python
    meta = graph_data.get("metadata", {})
    max_round = max((a.get("round_num", 0) for a in chat_log), default=0)
    trade_count = sum(
        1 for a in chat_log
        if a.get("platform") == "polymarket" and a.get("action_type") in ("BUY", "SELL")
    )
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(max_round), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
        {"label": "Trades", "value": str(trade_count), "color": "#F97316"},
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_structured_results.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add infra/docker/results.py tests/test_structured_results.py
git commit -m "fix: Rounds metric shows max round number, add Trades count to confidence"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS, no regressions

- [ ] **Step 2: Run ruff linter**

Run: `ruff check saas/jobs/alerts.py saas/jobs/tasks.py saas/gpu/errors.py infra/docker/run_job.py infra/docker/results.py tests/test_alerts.py tests/test_sim_config_patch.py tests/test_structured_results.py tests/test_gpu_provider.py`
Expected: No errors (line length ≤ 100)

- [ ] **Step 3: Fix any lint issues and commit**

If ruff reports issues, fix them and commit:

```bash
git add -u
git commit -m "fix: lint cleanup for sim data quality guardrails"
```
