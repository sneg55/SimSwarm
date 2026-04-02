---
title: Live Pod Progress — Surface Round Counts & Agent Activity During Simulation
date: 2026-04-02
status: approved
---

## Overview

While a simulation is running, the status page shows only coarse stage info (0 of 5) and a time-estimated progress bar. The GPU pod has richer data available — round counters, log milestones, and a growing `chat_log.json` — but none of it reaches the frontend. This spec adds a `live_status` DB column, increases worker polling frequency, and surfaces round counts + a live agent feed in the UI.

---

## 1. Data Model

### New column: `simulation_jobs.live_status` (JSONB, nullable)

Written by the Celery worker during job execution. Read by `getJob` and included in the existing job API response.

Schema:
```json
{
  "round": 47,
  "max_rounds": 200,
  "log_lines": ["[pipeline] 12 entities extracted", "[pipeline] Building knowledge graph"],
  "partial_chat": [
    { "role": "agent", "content": "...", "agent_id": "agent_47", ... }
  ],
  "updated_at": 1712345678.0
}
```

- `round` / `max_rounds`: extracted from pipeline log lines via regex
- `log_lines`: last 3 non-noisy lines (filtered: blank, vLLM HTTP access logs, internal framework noise)
- `partial_chat`: last 10 chat messages from the pod's `/partial_chat` endpoint; only populated when `pipeline_stage >= 3`
- `updated_at`: monotonic timestamp of last write; lets the frontend detect stale data

### Migration

Add `live_status = Column(JSONB, nullable=True)` to `SimulationJob`. Alembic migration required.

---

## 2. Backend: Worker Polling Uplift

### `saas/workers/job_runner.py`

**Polling frequency:** Reduce log/chat poll interval from every 60s (`poll % 6 == 0`) to every 2 poll cycles (~20s, `poll % 2 == 0`). The 10s base poll interval is unchanged.

**Log extraction:**
- Fetch `/logs?tail=20&source=pipeline`
- Filter lines: skip empty, skip lines matching `GET /` or `POST /` (HTTP access log noise), skip lines shorter than 10 chars
- Keep last 3 cleaned lines as `log_lines`
- Extract round count: `re.search(r'round[=\s]+(\d+)', line, re.IGNORECASE)` — use the highest match found across all lines

**Partial chat:**
- Only when `pipeline_stage >= 3`
- Fetch `/partial_chat?tail=10` from pod (see §3)
- Store as `partial_chat` in `live_status`
- On failure (endpoint not ready, JSON parse error): store `[]`, do not fail the poll

**DB write:**
- Use sync psycopg2 (per existing pattern for Celery DB writes — never the shared async pool)
- Write `live_status` column only; do not touch other job fields
- Skip write if round, log_lines, and partial_chat message count are all identical to the last write (track in local variables `_last_round`, `_last_log_lines`, `_last_chat_count` within the polling loop)

### Stage detection improvement

Current `_infer_pipeline_stage` only checks log lines fetched every 60s. With 20s polling, stage transitions will be caught ~3× faster. No logic change needed — the increased frequency is sufficient.

---

## 3. Pod: `/partial_chat` Endpoint

### `infra/docker/worker_api.py`

Add a new endpoint:

```python
@app.route("/partial_chat", methods=["GET"])
def partial_chat():
    path = Path("/tmp/results/chat_log.json")
    if not path.exists():
        return jsonify({"messages": []})
    tail = request.args.get("tail", 20, type=int)
    try:
        data = json.loads(path.read_text())
        messages = data[-tail:] if isinstance(data, list) else []
    except Exception:
        messages = []
    return jsonify({"messages": messages})
```

This reads the file that `run_job.py` writes incrementally. If the file is mid-write (partial JSON), the `except` clause catches the parse error and returns `[]` gracefully.

---

## 4. API: `getJob` Response

No new endpoints. `live_status` is included in the existing `GET /jobs/{id}` response (the column is on the model, SQLAlchemy serializes it automatically via the existing job schema).

The frontend polls `getJob` every 3s already — no polling change needed.

---

## 5. Frontend

### Progress card — Rounds row

In the `isActive` block of `SimulationStatus.vue`, add a "Rounds" row below the ETA row:

```
Rounds    47 / 200
```

- Visible only when `job.live_status?.round` is present AND `job.pipeline_stage === 3`
- Uses `font-mono tabular-nums` styling consistent with other rows
- `max_rounds` sourced from `live_status.max_rounds`; fallback to tier-based estimate if absent

The progress bar remains time-based. Round progress is noisier (agents can pause mid-round) and the time bar already gives a smooth visual — the Rounds row provides the precise signal.

### New component: `LiveActivity.vue`

Props:
- `logLines: string[]`
- `partialChat: object[]`
- `stage: number`

Visibility: rendered in `SimulationStatus.vue` when `isActive && (logLines.length > 0 || partialChat.length > 0)`. Appears below the progress card, above the email banner.

**Collapsible:** default open when it first appears. User can collapse. State not persisted (resets on page load).

**Log lines section** (shown when `stage < 3` or when `partialChat` is empty):
- Simple list of 3 lines, `font-mono text-xs text-mist-drift`
- Each line prefixed with a `·` bullet
- No timestamps (log lines already have context)

**Agent feed section** (shown when `partialChat.length > 0`):
- Reuses the message row rendering from `ChatReplay.vue` (extract or share the row component)
- Latest message has a pulsing teal "LIVE" badge: `animate-[breathe_2.5s_ease-in-out_infinite]` dot + "LIVE" text in `text-ocean-glow`
- Older messages render identically to finished chat replay
- Maximum 10 messages shown; scrollable if overflow

**Transition to completion:** when `job.status === 'COMPLETED'`, `LiveActivity` unmounts and the existing full `ChatReplay` takes over. No animated transition needed — the page naturally re-renders into the completed layout.

---

## 6. Error Handling & Edge Cases

- **Pod not reachable during poll:** log warning, skip `live_status` write, continue polling. Do not fail the job.
- **`/partial_chat` endpoint missing** (old pod image): `httpx` will return 404; catch and treat as `[]`. Old pods without the endpoint degrade gracefully — users just won't see partial chat.
- **Stale `live_status`:** frontend checks `updated_at`; if > 120s old, suppress the Rounds row and Live Activity (pod may be stalled). Show "--" for round count.
- **`chat_log.json` mid-write:** `json.loads` will throw; pod endpoint returns `[]`. Harmless.
- **Job completes before first live_status write:** `live_status` is null; frontend simply doesn't show the new UI elements. No breakage.

---

## 7. What's Not In Scope

- Streaming log lines directly to the browser (SSE proxy) — too complex for marginal latency gain
- vLLM logs in the UI — too noisy, not user-meaningful
- Round-based progress bar — round progress is too noisy; time-based bar stays
- Persisting partial chat after job completion — full `chat_log` is already stored; partial is ephemeral

---

## 8. Testing

- Unit test `_extract_live_status(log_lines)` helper (round regex, noise filtering)
- Integration test: mock pod `/logs` and `/partial_chat` responses; assert `live_status` DB column is written correctly
- Frontend: Vitest test for `LiveActivity.vue` — renders log lines, renders agent feed, "LIVE" badge on latest message only, hides when `logLines` and `partialChat` are both empty
