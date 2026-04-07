# Simulation Data Quality Guardrails

**Date:** 2026-04-07
**Trigger:** Sim 62 — completed successfully but produced 3 graph entities, 4 agents, 9 actions in 1 round, 0 trades, misleading metrics.

## Problem Analysis

Sim 62 (Apple AI ecosystem, small tier) completed with garbage output due to a chain of failures:

1. **Enrichment failed silently** — `enrich_web=true` but xAI Grok returned nothing. No alert fired. The GPU worker received a raw 280-char seed with no background research.
2. **Tiny knowledge graph** — Qwen3-14B extracted only 3 entities (Apple Intelligence, Craig Federighi, Tim Cook) from the short unenriched seed. Samsung, Google, Meta, T.M. Roh, etc. all missed.
3. **Few agents** — 3 graph entities produced only 4 agents.
4. **10 rounds instead of 200** — `max_rounds` is a ceiling, not a target. The LLM-generated `time_config` produced `total_rounds = (total_hours * 60) / minutes_per_round` which was ~10. `min(10, 200) = 10`.
5. **Off-peak starvation** — All 10 rounds fell in simulated midnight hours. The `off_peak_activity_multiplier = 0.05` meant `target_count = random.uniform(5,20) * 0.05 ≈ 0-1` agents per round. Only round 10 got lucky and activated all 4 agents.
6. **Zero trades** — The single Polymarket action was CREATE_MARKET in round 10 (the last round). No subsequent round existed for agents to trade.
7. **Misleading metrics** — "Rounds" displayed `len(chat_log)` (9 actions) instead of the actual round count. No distinction between CREATE_MARKET and BUY/SELL in trade counts.

## Design

Five changes across two layers (SaaS backend + GPU worker). None modify `vendor/mirofish/`.

### Section 1: Enrichment Failure Alerting

**Where:** `saas/jobs/tasks.py` (after enrichment call, ~line 76) + new function in `saas/jobs/alerts.py`

**What:** When `enrich_web=True` but `enrich_seed()` returns `None`, fire a webhook alert to `ALERT_WEBHOOK_URL`. The job still proceeds (enrichment is best-effort), but operators get visibility.

New function:
```python
# saas/jobs/alerts.py
def send_enrichment_alert(job_id: int, goal: str) -> None:
    """Alert when enrichment was requested but returned nothing."""
```

Message format: `:warning: Enrichment Failed — Job {job_id}: enrichment requested but returned empty. Goal: "{goal[:100]}"`

**No behavioral change** to the pipeline — just visibility.

### Section 2: Minimum Entity Guard

**Where:** `infra/docker/run_job.py` in `run_pipeline()`, after `build_graph()` and before `prepare_simulation()`.

**What:** Check graph node count. If < 5 entities, raise a specific error that triggers fail + refund on the SaaS side.

```python
MIN_GRAPH_ENTITIES = 5

info = storage.get_graph_info(graph_id)
node_count = info.get("node_count", 0)
if node_count < MIN_GRAPH_ENTITIES:
    raise RuntimeError(
        f"GRAPH_TOO_SMALL: only {node_count} entities extracted "
        f"(minimum {MIN_GRAPH_ENTITIES})"
    )
```

**SaaS side:** In `saas/gpu/errors.py`, classify `GRAPH_TOO_SMALL` as a **permanent** error (no retry → fail + refund).

The `finally` block in `run_pipeline()` already handles Neo4j graph cleanup on any exit path.

### Section 3: Fix Simulation Round Count and Activity

**Where:** `infra/docker/run_job.py` in `run_pipeline()`, after `prepare_simulation()` returns and before `run_and_wait()`.

**Root cause:** Two compounding bugs in the MiroFish engine config:
- `max_rounds` is a ceiling, not a target — actual rounds come from `time_config.total_simulation_hours / minutes_per_round`
- `off_peak_activity_multiplier = 0.05` suppresses almost all agent activity during simulated midnight hours

**Fix:** Patch the generated `simulation_config.json` before the simulation starts:

1. **Ensure enough rounds:** Read the config, calculate `config_rounds = (total_hours * 60) / minutes_per_round`. If `config_rounds < max_rounds`, increase `total_simulation_hours` so the calculation yields `>= max_rounds` rounds.

2. **Clamp off-peak multiplier:** Set `off_peak_activity_multiplier = max(0.3, current_value)` so agents still participate during off-peak hours. Original value (0.05) makes agents virtually inactive 6 hours/day.

This patches the config file that `vendor/mirofish/` reads — no engine modifications.

### Section 4: Fix "Rounds" Metric

**Where:** `infra/docker/results.py`, `build_structured_results()` line 242.

**Current:**
```python
{"label": "Rounds", "value": str(len(chat_log)), ...}
```
Shows total action count (9), not round count.

**Fix:**
```python
{"label": "Rounds", "value": str(max((a.get("round_num", 0) for a in chat_log), default=0)), ...}
```
Shows the highest round number from the chat log.

### Section 5: Add Trade Count to Confidence Metrics

**Where:** `infra/docker/results.py`, `build_structured_results()` after the confidence array.

**What:** Add a 4th confidence entry counting actual BUY/SELL trades (excluding CREATE_MARKET):

```python
trade_count = sum(
    1 for a in chat_log
    if a.get("platform") == "polymarket"
    and a.get("action_type") in ("BUY", "SELL")
)
confidence.append(
    {"label": "Trades", "value": str(trade_count), "color": "#F97316"}
)
```

This is a nice-to-have. The real fix for zero trades is section 3 — with 200 rounds and active agents, markets get created early and agents have many rounds to trade.

## Files Changed

| File | Change |
|---|---|
| `saas/jobs/alerts.py` | Add `send_enrichment_alert()` |
| `saas/jobs/tasks.py` | Call alert on enrichment failure |
| `saas/gpu/errors.py` | Classify GRAPH_TOO_SMALL as permanent |
| `infra/docker/run_job.py` | Add MIN_GRAPH_ENTITIES guard + time_config patch |
| `infra/docker/results.py` | Fix Rounds metric + add Trades confidence entry |

## Not Changed

- `vendor/mirofish/` — architecture rules prohibit direct modification
- Frontend — metrics are already rendered from the confidence array; new values appear automatically
- Database schema — no new columns needed
