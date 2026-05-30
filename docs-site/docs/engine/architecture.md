---
sidebar_label: Architecture
---

# Engine architecture

The SimSwarm engine (`simswarm/`) is a pure-Python, async, framework-free simulation core.
It has no infrastructure dependencies (no database, no Celery, no HTTP framework), so the
library can be driven standalone or wrapped by the SaaS worker. The only external calls are
to an OpenAI-compatible chat endpoint via `simswarm.llm.LLMClient`.

The public surface is `simswarm.engine.Engine`, which orchestrates rounds, agents, and
environments. The plain dataclasses it operates on live in `simswarm/types.py`.

## Core types

`simswarm/types.py` defines everything as plain dataclasses (no framework deps):

- `Agent`: `id`, `name`, `persona` (a system-prompt string), `environments` (list of env
  names it acts in), `belief_state`, `config` (`AgentActivityConfig`), and a `memory` list.
- `BeliefState`: `positions` (topic → `[-1, 1]`), `confidence` (topic → `[0, 1]`), `trust`
  (author name → `[0, 1]`), and `exposure_history` (a set of content hashes).
- `Action` / `ActionResult`: an agent's intended action and an environment's response.
- `ActionRecord`: the logged row appended to the chat log (round, agent, action_type,
  platform, `action_args`, `success`, `action_result`).
- `SimulationConfig`: the full run input: `seed_text`, `goal`, `entities`, `environments`,
  `rounds`, `concurrency`, `variables`, `scheduled_events`, `enrichment`.
- `EngineConfig`: engine-level knobs: `max_memory_rounds=20`, `concurrency=32`,
  `context_budget=16384`, `flush_interval=10`, `checkpoint_interval=50`.
- `SimulationResult`: the output: `chat_log`, `graph_data` (a `GraphSnapshot`),
  `trajectories`, `market_data`, `raw_state`.
- `Tool`: an action exposed by an environment as an LLM tool, with `to_openai_schema()`.

## Constructing the engine

```python
class Engine:
    def __init__(self, fast_llm: LLMClient, smart_llm: LLMClient,
                 engine_config: EngineConfig | None = None): ...
```

Two LLM clients are injected. The fast client drives the per-round agent loop (it makes
the bulk of the calls). The smart client is reserved for the heavier offline analysis
steps (entity/relation/persona extraction and report writing) that run outside `Engine.run`.

## The round loop

`Engine.run(config, on_progress=None, on_round=None)` runs the simulation. Setup:

1. `_create_environments(config.environments)` instantiates one environment per
   `EnvironmentConfig` (`social`, `market`, `economic`). If none are configured it defaults
   to a single `SocialEnvironment`.
2. `_create_agents(config.entities, env_names)` turns each `Entity` into an `Agent`. The
   persona is seeded inline as `f"You are {entity.name}. {entity.summary}"`, and every agent
   is granted access to every environment.
3. A `Bridge` (see below), the `chat_log`, the `snapshots` list, and an
   `asyncio.Semaphore(config.concurrency)` are created.
4. `belief_topic` is derived once from the goal: `(config.goal or "topic").strip()[:200] or "topic"`.
   Belief dynamics treat the whole sim as a single topic.

Then, for each round `1..config.rounds`:

1. **Inject scheduled events:** `bridge.inject_scheduled(config.scheduled_events, round_num)`
   queues any `ScheduledEvent` whose `round` matches.
2. **Gather observations:** for every agent, collect one `Observation` per environment it
   belongs to (`env.get_observations(agent)`), plus a bridge digest of cross-environment
   events, plus a `scenario` observation rendering `config.variables` if present. These are
   stored in `agent_observations[agent.id]` *before* any LLM call, so all agents observe the
   same pre-step world state (synchronous within a round).
3. **Concurrency-gated agent steps:** `step_agent` is defined as a coroutine and run for all
   agents via `asyncio.gather`. Each invocation acquires the semaphore (`async with
   semaphore:`) so at most `config.concurrency` LLM calls are in flight at once. Inside:
   - Build the tool list by union-ing `env.get_tools()` across the agent's environments and
     converting each to an OpenAI schema (`Tool.to_openai_schema()`).
   - Build the message list with `build_context(agent, obs)` and call
     `self.fast_llm.chat(messages, tools=tool_schemas)`.
   - For each returned tool call, resolve the owning environment with
     `_find_env_for_action`, build an `Action`, execute it (`env.execute_action`), and append
     an `ActionRecord` capturing `success` and `action_result`.
   - Append a memory line `f"Round {n}: {action}({args})"`, then trim memory to the last
     `max_memory_rounds`.
   - If the LLM returned **no** tool calls, a synthetic `do_nothing` `ActionRecord` is logged.
4. **Belief update:** gather a `{post_id: (likes, dislikes)}` lookup by calling
   `env.current_engagement()` on any environment that exposes it, then
   `apply_belief_updates(agents, round_records, belief_topic, likes_lookup=...)`. See
   [Belief formulation](belief-formulation.md).
5. **Tick:** `env.tick()` on every environment (advances `current_round`, recomputes
   metrics, queues virality/price-move/metric-change events).
6. **Bridge events:** collect `env.publish_events()` from all environments and hand them to
   `bridge.receive_events(...)` for next round's digests.
7. **Snapshot:** append a `RoundSnapshot` with `metrics={"actions": <count>}`.
8. **Callbacks:** `await on_round(round_num, chat_log)` and
   `await on_progress(round_num, config.rounds, metrics)` if provided.
9. **Clear:** `bridge.clear()` empties pending events so digests don't accumulate.

After the last round, `run` returns a `SimulationResult` whose `graph_data` is built inline
via `build_graph(list(config.entities), chat_log)` (no LLM relations at this stage; those
are merged on-pod by the job runner after `Engine.run` returns; see
[Graph build](graph-build.md)) and whose `raw_state` carries
the final agents, environments, and snapshots.

## Action to environment routing

`_find_env_for_action(action_name, environments, agent)` walks the agent's environments in
order and returns the first one whose `get_tools()` set contains a tool named `action_name`.
If no environment claims the action, it falls back to the agent's first environment (or
`"unknown"`). This is why tool names must be unique enough across environments to route
correctly: the first matching environment wins.

## Concurrency model

There is exactly one semaphore, sized by `config.concurrency` (defaulting to
`EngineConfig.concurrency = 32`). All agents for a round are dispatched at once via
`asyncio.gather`, but only `concurrency` of them hold the semaphore, and therefore an
in-flight LLM request, simultaneously. Observations are computed up front for the whole
round, so an agent never sees another agent's *same-round* action; cross-round visibility is
what drives the dynamics. Environment state mutations from `execute_action` happen as each
agent's tool calls resolve, but because the feed each agent saw was snapshotted before the
gather, the round is effectively simultaneous from each agent's perspective.

## The cross-environment bridge

`simswarm/bridge.py` decouples environments from each other. Each environment publishes
typed `Event`s (`viral_post`, `price_move`, `policy_change`, `metric_change`); the `Bridge`
collects them and, in the next round, renders a per-agent digest of events whose `source`
is an environment the agent is *not* directly in (`get_digest` filters out same-source events
so an agent isn't told twice about its own platform). `_format_event` renders human-readable
one-liners, e.g. `[Social] Trending: "..." by <author>` or `[Market] <q> moved up to 63%`.
Scheduled events are injected with `source="scheduled"`.

## The output adapter

`simswarm/adapter.py` is the contract bridge to the SaaS worker. `adapt_chat_log` and
`adapt_graph_data` serialize the dataclasses to the exact `{...}` / `{nodes, edges,
metadata}` shapes the frontend consumes (agent_id stays a string). `adapt_structured`
assembles the final results dict by merging an LLM brief/verdict/findings with the
deterministic signals from `build_story_signals(...)`; see [Story signals](story-signals.md).
`FINDING_COLORS` supplies fallback accent colors when the LLM omits them.

## Sweeps

`Engine.run_sweep(sweep, on_progress=None)` expands a `ScenarioSweep` into configs via
`generate_sweep_configs` and runs them **sequentially**, returning
`list[tuple[key, SimulationResult]]`. See [Sweeps](sweeps.md).
