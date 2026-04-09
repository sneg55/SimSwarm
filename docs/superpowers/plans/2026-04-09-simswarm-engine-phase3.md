# SimSwarm Engine Phase 3 — Migration & Report Module

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the SimSwarm engine to the GPU pod pipeline — output adapter, rich data extractor, report module, and new run_job that replaces MiroShark's simulation step while keeping graph building intact.

**Architecture:** Graph building still uses MiroShark (OntologyGenerator, TextProcessor, Neo4jStorage) — it's graph tooling, not simulation logic. The simulation step swaps to SimSwarm engine. A new output adapter converts `SimulationResult` to the JSON format the worker API expects. Report generation moves to a lean module with tool access over the result data.

**Tech Stack:** Python 3.11+, asyncio, aiohttp, Jinja2, Neo4j driver (existing), pytest

**Spec:** `docs/superpowers/specs/2026-04-09-simswarm-engine-rewrite-design.md`
**Phase 2 plan:** `docs/superpowers/plans/2026-04-09-simswarm-engine-rewrite.md`

---

## File Structure

```
simswarm/
  environments/
    economic.py         # NEW — v1 economic environment
  report.py             # NEW — lean report generator with tool access
  adapter.py            # NEW — SimulationResult → MiroShark-compatible JSON
  extractor.py          # NEW — rich sim data from engine state (replaces SQLite extraction)
infra/docker/
  run_job_v2.py         # NEW — pipeline using SimSwarm engine
  worker_api.py         # MODIFY — add engine_version toggle
tests/
  engine/
    test_economic_env.py  # NEW
    test_adapter.py       # NEW
    test_extractor.py     # NEW
    test_report.py        # NEW
    test_run_job_v2.py    # NEW
```

---

### Task 1: Economic Environment (v1)

The grant-enabling environment. Agents represent economic actors with actions like hire, invest, set_price. Aggregate metrics update via rule-based formulas.

**Files:**
- Create: `simswarm/environments/economic.py`
- Create: `tests/engine/test_economic_env.py`
- Modify: `simswarm/environments/__init__.py`

- [ ] **Step 1: Write economic environment tests**

```python
# tests/engine/test_economic_env.py
"""Test economic environment: firms, workers, investors, policy, aggregate metrics."""
from __future__ import annotations

import pytest

from simswarm.environments.economic import EconomicEnvironment, EconomicConfig
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Firm", agent_type: str = "firm") -> Agent:
    return Agent(
        id=agent_id, name=name, persona=f"You are a {agent_type}.",
        environments=["economic"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestFirmActions:
    def test_set_price_updates_firm_state(self):
        env = EconomicEnvironment(EconomicConfig())
        firm = _make_agent("f1", "AcmeCorp", "firm")
        env.register_agent(firm, role="firm", balance=10000.0)
        result = env.execute_action(firm, Action(
            agent_id="f1", environment="economic",
            action_type="set_price", args={"price": 25.0},
        ))
        assert result.success
        assert env.actors["f1"].price == 25.0

    def test_hire_increases_workforce(self):
        env = EconomicEnvironment(EconomicConfig())
        firm = _make_agent("f1", "AcmeCorp", "firm")
        env.register_agent(firm, role="firm", balance=10000.0)
        result = env.execute_action(firm, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 5},
        ))
        assert result.success
        assert env.actors["f1"].workforce == 5

    def test_fire_decreases_workforce(self):
        env = EconomicEnvironment(EconomicConfig())
        firm = _make_agent("f1", "AcmeCorp", "firm")
        env.register_agent(firm, role="firm", balance=10000.0)
        env.actors["f1"].workforce = 10
        result = env.execute_action(firm, Action(
            agent_id="f1", environment="economic",
            action_type="fire", args={"count": 3},
        ))
        assert result.success
        assert env.actors["f1"].workforce == 7

    def test_fire_cannot_go_negative(self):
        env = EconomicEnvironment(EconomicConfig())
        firm = _make_agent("f1", "AcmeCorp", "firm")
        env.register_agent(firm, role="firm", balance=10000.0)
        env.actors["f1"].workforce = 2
        result = env.execute_action(firm, Action(
            agent_id="f1", environment="economic",
            action_type="fire", args={"count": 5},
        ))
        assert result.success
        assert env.actors["f1"].workforce == 0


class TestInvestorActions:
    def test_invest_transfers_capital(self):
        env = EconomicEnvironment(EconomicConfig())
        investor = _make_agent("i1", "VentureCapital", "investor")
        firm = _make_agent("f1", "AcmeCorp", "firm")
        env.register_agent(investor, role="investor", balance=100000.0)
        env.register_agent(firm, role="firm", balance=5000.0)
        result = env.execute_action(investor, Action(
            agent_id="i1", environment="economic",
            action_type="invest", args={"target": "f1", "amount": 20000.0},
        ))
        assert result.success
        assert env.actors["i1"].balance == 80000.0
        assert env.actors["f1"].balance == 25000.0


class TestPolicyActions:
    def test_apply_policy_records_active_policy(self):
        env = EconomicEnvironment(EconomicConfig())
        gov = _make_agent("g1", "Government", "policymaker")
        env.register_agent(gov, role="policymaker", balance=0.0)
        result = env.execute_action(gov, Action(
            agent_id="g1", environment="economic",
            action_type="apply_policy",
            args={"policy": "stimulus", "details": "50B infrastructure spending"},
        ))
        assert result.success
        assert len(env.active_policies) == 1
        assert env.active_policies[0]["policy"] == "stimulus"


class TestAggregateMetrics:
    def test_tick_computes_employment_rate(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=100))
        f1 = _make_agent("f1", "Firm1", "firm")
        f2 = _make_agent("f2", "Firm2", "firm")
        env.register_agent(f1, role="firm", balance=10000.0)
        env.register_agent(f2, role="firm", balance=10000.0)
        env.actors["f1"].workforce = 30
        env.actors["f2"].workforce = 50
        env.tick()
        assert env.metrics["employment_rate"] == pytest.approx(0.8)

    def test_tick_computes_average_price(self):
        env = EconomicEnvironment(EconomicConfig())
        f1 = _make_agent("f1", "Firm1", "firm")
        f2 = _make_agent("f2", "Firm2", "firm")
        env.register_agent(f1, role="firm", balance=10000.0)
        env.register_agent(f2, role="firm", balance=10000.0)
        env.actors["f1"].price = 20.0
        env.actors["f2"].price = 30.0
        env.tick()
        assert env.metrics["avg_price"] == pytest.approx(25.0)

    def test_tick_publishes_event_on_metric_change(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=100))
        f1 = _make_agent("f1", "Firm1", "firm")
        env.register_agent(f1, role="firm", balance=10000.0)
        env.actors["f1"].workforce = 80
        env.tick()
        env.actors["f1"].workforce = 50
        env.tick()
        events = env.publish_events()
        metric_events = [e for e in events if e.type == "metric_change"]
        assert len(metric_events) >= 1


class TestObservations:
    def test_observations_include_metrics_and_policies(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=100))
        f1 = _make_agent("f1", "Firm1", "firm")
        env.register_agent(f1, role="firm", balance=10000.0)
        env.actors["f1"].workforce = 80
        env.tick()
        obs = env.get_observations(f1)
        assert "employment" in obs.content.lower() or "80" in obs.content

    def test_observations_include_scenario_variables(self):
        env = EconomicEnvironment(EconomicConfig())
        env.scenario_variables = {"wealth_fund_size": "2T", "distribution_model": "cash"}
        agent = _make_agent("f1", "Firm1", "firm")
        env.register_agent(agent, role="firm", balance=10000.0)
        obs = env.get_observations(agent)
        assert "wealth_fund_size" in obs.content


class TestTools:
    def test_get_tools_returns_all_actions(self):
        env = EconomicEnvironment(EconomicConfig())
        tools = env.get_tools()
        names = {t.name for t in tools}
        assert "set_price" in names
        assert "hire" in names
        assert "fire" in names
        assert "invest" in names
        assert "apply_policy" in names
        assert "do_nothing" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_economic_env.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the economic environment**

```python
# simswarm/environments/economic.py
"""Economic environment — agents as firms, workers, investors, policymakers.

Aggregate metrics (employment, prices, output) update via rule-based
formulas each round. Policy variables injected via scenario config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


@dataclass
class EconomicConfig:
    labor_force: int = 1000
    metric_change_threshold: float = 0.05


@dataclass
class EconomicActor:
    """State for an economic agent."""
    agent_id: str
    role: str  # firm, worker, investor, policymaker
    balance: float = 0.0
    workforce: int = 0
    price: float = 10.0
    output: float = 0.0


class EconomicEnvironment:
    """Simplified economy with firms, investors, policymakers."""

    name = "economic"

    def __init__(self, config: EconomicConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.actors: dict[str, EconomicActor] = {}
        self.active_policies: list[dict[str, Any]] = []
        self.metrics: dict[str, float] = {
            "employment_rate": 0.0,
            "avg_price": 0.0,
            "total_output": 0.0,
            "total_investment": 0.0,
        }
        self._prev_metrics: dict[str, float] = dict(self.metrics)
        self._pending_events: list[Event] = []
        self.scenario_variables: dict[str, Any] = {}

    def register_agent(self, agent: Agent, role: str = "firm", balance: float = 0.0) -> None:
        self.actors[agent.id] = EconomicActor(
            agent_id=agent.id, role=role, balance=balance,
        )

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
        if agent.id not in self.actors:
            self.register_agent(agent)
        handler = {
            "set_price": self._handle_set_price,
            "hire": self._handle_hire,
            "fire": self._handle_fire,
            "invest": self._handle_invest,
            "allocate": self._handle_allocate,
            "apply_policy": self._handle_apply_policy,
            "do_nothing": self._handle_noop,
        }.get(action.action_type)
        if handler is None:
            return ActionResult(success=False, data={"error": f"Unknown action: {action.action_type}"})
        return handler(agent, action.args)

    def get_observations(self, agent: Agent) -> Observation:
        lines = ["--- ECONOMIC STATE ---"]
        lines.append(f"Employment rate: {self.metrics['employment_rate']:.1%}")
        lines.append(f"Average price level: ${self.metrics['avg_price']:.2f}")
        lines.append(f"Total output: {self.metrics['total_output']:.0f}")

        if self.active_policies:
            lines.append("\nActive policies:")
            for p in self.active_policies:
                lines.append(f"  - {p['policy']}: {p.get('details', '')}")

        if self.scenario_variables:
            lines.append("\nScenario variables:")
            for k, v in self.scenario_variables.items():
                lines.append(f"  {k}: {v}")

        actor = self.actors.get(agent.id)
        if actor:
            lines.append(f"\nYour role: {actor.role}")
            lines.append(f"Your balance: ${actor.balance:.2f}")
            if actor.role == "firm":
                lines.append(f"Workforce: {actor.workforce}")
                lines.append(f"Price: ${actor.price:.2f}")

        return Observation(environment=self.name, content="\n".join(lines))

    def get_tools(self) -> list[Tool]:
        return [
            Tool(name="set_price", description="Set the price for your goods/services",
                 parameters={"type": "object", "properties": {
                     "price": {"type": "number", "description": "New price"},
                 }, "required": ["price"]}),
            Tool(name="hire", description="Hire workers",
                 parameters={"type": "object", "properties": {
                     "count": {"type": "integer", "description": "Number of workers to hire"},
                 }, "required": ["count"]}),
            Tool(name="fire", description="Lay off workers",
                 parameters={"type": "object", "properties": {
                     "count": {"type": "integer", "description": "Number of workers to fire"},
                 }, "required": ["count"]}),
            Tool(name="invest", description="Invest capital in a target firm",
                 parameters={"type": "object", "properties": {
                     "target": {"type": "string", "description": "Agent ID of the firm"},
                     "amount": {"type": "number", "description": "USD to invest"},
                 }, "required": ["target", "amount"]}),
            Tool(name="allocate", description="Allocate resources or funds",
                 parameters={"type": "object", "properties": {
                     "target": {"type": "string"},
                     "amount": {"type": "number"},
                     "purpose": {"type": "string"},
                 }, "required": ["target", "amount"]}),
            Tool(name="apply_policy", description="Enact a policy (policymakers only)",
                 parameters={"type": "object", "properties": {
                     "policy": {"type": "string", "description": "Policy name"},
                     "details": {"type": "string", "description": "Policy details"},
                 }, "required": ["policy"]}),
            Tool(name="do_nothing", description="Take no action this round",
                 parameters={"type": "object", "properties": {}}),
        ]

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def tick(self) -> None:
        self.current_round += 1
        self._prev_metrics = dict(self.metrics)

        # Compute employment rate
        firms = [a for a in self.actors.values() if a.role == "firm"]
        total_employed = sum(f.workforce for f in firms)
        if self.config.labor_force > 0:
            self.metrics["employment_rate"] = total_employed / self.config.labor_force

        # Compute average price
        prices = [f.price for f in firms if f.price > 0]
        self.metrics["avg_price"] = sum(prices) / len(prices) if prices else 0.0

        # Compute total output (workforce * price as proxy)
        self.metrics["total_output"] = sum(f.workforce * f.price for f in firms)

        # Check for significant metric changes → publish events
        for key in self.metrics:
            prev = self._prev_metrics.get(key, 0.0)
            curr = self.metrics[key]
            if prev > 0 and abs(curr - prev) / prev >= self.config.metric_change_threshold:
                self._pending_events.append(Event(
                    source=self.name, type="metric_change",
                    data={"metric": key, "previous": prev, "current": curr,
                          "delta": curr - prev},
                    round=self.current_round,
                ))

    # --- Handlers ---

    def _handle_set_price(self, agent: Agent, args: dict) -> ActionResult:
        price = args.get("price", 0.0)
        if price < 0:
            return ActionResult(success=False, data={"error": "Price cannot be negative"})
        self.actors[agent.id].price = price
        return ActionResult(success=True, data={"price": price})

    def _handle_hire(self, agent: Agent, args: dict) -> ActionResult:
        count = args.get("count", 0)
        self.actors[agent.id].workforce += max(0, count)
        return ActionResult(success=True, data={"workforce": self.actors[agent.id].workforce})

    def _handle_fire(self, agent: Agent, args: dict) -> ActionResult:
        count = args.get("count", 0)
        actor = self.actors[agent.id]
        actor.workforce = max(0, actor.workforce - count)
        return ActionResult(success=True, data={"workforce": actor.workforce})

    def _handle_invest(self, agent: Agent, args: dict) -> ActionResult:
        target_id = args.get("target", "")
        amount = args.get("amount", 0.0)
        if target_id not in self.actors:
            return ActionResult(success=False, data={"error": "Target not found"})
        investor = self.actors[agent.id]
        if investor.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})
        investor.balance -= amount
        self.actors[target_id].balance += amount
        self.metrics["total_investment"] += amount
        return ActionResult(success=True, data={"invested": amount, "target": target_id})

    def _handle_allocate(self, agent: Agent, args: dict) -> ActionResult:
        target_id = args.get("target", "")
        amount = args.get("amount", 0.0)
        if target_id not in self.actors:
            return ActionResult(success=False, data={"error": "Target not found"})
        actor = self.actors[agent.id]
        if actor.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})
        actor.balance -= amount
        self.actors[target_id].balance += amount
        return ActionResult(success=True, data={"allocated": amount})

    def _handle_apply_policy(self, agent: Agent, args: dict) -> ActionResult:
        policy = args.get("policy", "")
        details = args.get("details", "")
        self.active_policies.append({
            "policy": policy, "details": details,
            "round": self.current_round, "enacted_by": agent.id,
        })
        self._pending_events.append(Event(
            source=self.name, type="policy_change",
            data={"policy": policy, "details": details},
            round=self.current_round,
        ))
        return ActionResult(success=True, data={"policy": policy})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})
```

- [ ] **Step 4: Update environments/__init__.py**

Add to `simswarm/environments/__init__.py`:
```python
from simswarm.environments.economic import EconomicConfig, EconomicEnvironment
```

And add to `__all__`.

- [ ] **Step 5: Update engine.py to support economic environment**

In `simswarm/engine.py`, in the `_create_environments` method, add:
```python
elif ec.type == "economic":
    environments["economic"] = EconomicEnvironment(EconomicConfig(**ec.params))
```

Add the import at the top of engine.py:
```python
from simswarm.environments.economic import EconomicConfig, EconomicEnvironment
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/engine/test_economic_env.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add simswarm/environments/economic.py simswarm/environments/__init__.py simswarm/engine.py tests/engine/test_economic_env.py
git commit -m "feat: add v1 economic environment with firms, investors, policymakers"
```

---

### Task 2: Output Adapter

Converts `SimulationResult` to the exact JSON format the worker API returns. This is the contract bridge — the SaaS layer doesn't change.

**Files:**
- Create: `simswarm/adapter.py`
- Create: `tests/engine/test_adapter.py`

- [ ] **Step 1: Write adapter tests**

```python
# tests/engine/test_adapter.py
"""Test output adapter: SimulationResult → MiroShark-compatible JSON."""
from __future__ import annotations

import json

import pytest

from simswarm.adapter import adapt_chat_log, adapt_graph_data, adapt_structured
from simswarm.types import ActionRecord, GraphSnapshot
from tests.contracts.schemas import ChatLogEntry, GraphData, StructuredResults


SAMPLE_CHAT_LOG = [
    ActionRecord(round_num=1, agent_id="e1", agent_name="Alice", action_type="CREATE_POST",
                 platform="social", action_args={"text": "Hello"}, success=True),
    ActionRecord(round_num=2, agent_id="e2", agent_name="Bob", action_type="LIKE_POST",
                 platform="social", action_args={"post_id": "p1"}, success=True),
    ActionRecord(round_num=3, agent_id="e1", agent_name="Alice", action_type="do_nothing",
                 platform="social", action_args={}, success=True),
]

SAMPLE_GRAPH = GraphSnapshot(
    nodes=[
        {"uuid": "n1", "name": "Alice", "labels": ["Person"], "summary": "Analyst",
         "sentiment": 0.5, "stance": "supportive", "influence_weight": 1.5},
        {"uuid": "n2", "name": "Bob", "labels": ["Person"], "summary": "Reporter"},
    ],
    edges=[
        {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2",
         "name": "interacts_with", "fact": "Alice and Bob interact frequently"},
    ],
    metadata={"entity_types": ["Person"], "total_nodes": 2, "total_edges": 1},
)


class TestAdaptChatLog:
    def test_produces_list_of_dicts(self):
        result = adapt_chat_log(SAMPLE_CHAT_LOG)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_agent_id_is_integer(self):
        result = adapt_chat_log(SAMPLE_CHAT_LOG)
        for entry in result:
            assert isinstance(entry["agent_id"], int)

    def test_validates_against_contract_schema(self):
        result = adapt_chat_log(SAMPLE_CHAT_LOG)
        for entry in result:
            ChatLogEntry.model_validate(entry)

    def test_preserves_round_order(self):
        result = adapt_chat_log(SAMPLE_CHAT_LOG)
        rounds = [e["round_num"] for e in result]
        assert rounds == sorted(rounds)


class TestAdaptGraphData:
    def test_produces_valid_graph_data(self):
        result = adapt_graph_data(SAMPLE_GRAPH)
        GraphData.model_validate(result)

    def test_node_count_matches_metadata(self):
        result = adapt_graph_data(SAMPLE_GRAPH)
        assert len(result["nodes"]) == result["metadata"]["total_nodes"]

    def test_preserves_sentiment_and_stance(self):
        result = adapt_graph_data(SAMPLE_GRAPH)
        alice = next(n for n in result["nodes"] if n["name"] == "Alice")
        assert alice["sentiment"] == 0.5
        assert alice["stance"] == "supportive"


class TestAdaptStructured:
    def test_produces_valid_structured_results(self):
        result = adapt_structured(
            brief="Markets are volatile.",
            findings=[
                {"title": "Tariff Impact", "description": "New tariffs caused disruption."},
                {"title": "Recovery Signs", "description": "Some sectors showing resilience."},
            ],
            chat_log=SAMPLE_CHAT_LOG,
            graph_data=SAMPLE_GRAPH,
        )
        StructuredResults.model_validate(result)

    def test_brief_matches_input(self):
        result = adapt_structured(
            brief="Test brief.",
            findings=[],
            chat_log=[],
            graph_data=SAMPLE_GRAPH,
        )
        assert result["brief"] == "Test brief."

    def test_confidence_includes_agent_and_round_counts(self):
        result = adapt_structured(
            brief="Test.",
            findings=[],
            chat_log=SAMPLE_CHAT_LOG,
            graph_data=SAMPLE_GRAPH,
        )
        labels = {c["label"] for c in result["confidence"]}
        assert "Agents" in labels
        assert "Rounds" in labels
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_adapter.py -v`
Expected: FAIL

- [ ] **Step 3: Write the adapter**

```python
# simswarm/adapter.py
"""Output adapter: converts SimulationResult to MiroShark-compatible JSON.

The SaaS layer and frontend expect specific JSON shapes. This adapter
bridges SimSwarm's internal types to those shapes so the worker API
contract is preserved.
"""
from __future__ import annotations

from typing import Any

from simswarm.types import ActionRecord, GraphSnapshot

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]
CONFIDENCE_COLORS = ["#22D3EE", "#A78BFA", "#6EE7B7", "#F97316"]

POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success",
    "positive", "progress", "growth", "improve", "achieve", "gain",
    "agree", "optimistic", "strong", "stable", "recovery", "profit",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy",
    "negative", "decline", "loss", "risk", "recession", "collapse",
}


def _stable_int_id(agent_id: str) -> int:
    """Convert string agent_id to a stable integer for backwards compatibility."""
    return abs(hash(agent_id)) % 10**9


def adapt_chat_log(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Convert ActionRecords to MiroShark-compatible chat log dicts."""
    result = []
    for record in chat_log:
        result.append({
            "round_num": record.round_num,
            "agent_id": _stable_int_id(record.agent_id),
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "platform": record.platform,
            "action_args": record.action_args,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result


def adapt_graph_data(graph: GraphSnapshot) -> dict[str, Any]:
    """Convert GraphSnapshot to MiroShark-compatible graph data dict."""
    nodes = []
    for node in graph.nodes:
        nodes.append({
            "uuid": node.get("uuid", ""),
            "name": node.get("name", ""),
            "labels": node.get("labels", []),
            "summary": node.get("summary", ""),
            "connection_count": node.get("connection_count", 0),
            "sentiment": node.get("sentiment"),
            "stance": node.get("stance"),
            "influence_weight": node.get("influence_weight"),
        })
    edges = []
    for edge in graph.edges:
        edges.append({
            "uuid": edge.get("uuid", ""),
            "source_node_uuid": edge.get("source_node_uuid", ""),
            "target_node_uuid": edge.get("target_node_uuid", ""),
            "name": edge.get("name"),
            "fact": edge.get("fact"),
        })
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": graph.metadata,
    }


def adapt_structured(
    brief: str,
    findings: list[dict[str, str]],
    chat_log: list[ActionRecord],
    graph_data: GraphSnapshot,
) -> dict[str, Any]:
    """Build structured results matching the MiroShark format."""
    # Findings
    adapted_findings = []
    for i, f in enumerate(findings):
        adapted_findings.append({
            "label": "FINDING",
            "title": f.get("title", ""),
            "description": f.get("description", "")[:500],
            "metric": "",
            "accentColor": FINDING_COLORS[i % len(FINDING_COLORS)],
        })

    # Sentiment per platform
    platform_sentiment = _compute_platform_sentiment(chat_log)

    # Coalitions (simplified — from mutual interactions)
    coalitions = _detect_coalitions(chat_log)

    # Confidence grid
    agent_names = {r.agent_name for r in chat_log}
    rounds = {r.round_num for r in chat_log}
    trades = [r for r in chat_log if r.action_type in ("buy_shares", "sell_shares")]
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": CONFIDENCE_COLORS[0]},
        {"label": "Rounds", "value": str(max(rounds) if rounds else 0), "color": CONFIDENCE_COLORS[1]},
        {"label": "Graph Entities", "value": str(len(graph_data.nodes)), "color": CONFIDENCE_COLORS[2]},
        {"label": "Trades", "value": str(len(trades)), "color": CONFIDENCE_COLORS[3]},
    ]

    return {
        "brief": brief,
        "findings": adapted_findings,
        "sentiment": platform_sentiment,
        "coalitions": coalitions,
        "confidence": confidence,
    }


def _compute_platform_sentiment(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Compute per-platform sentiment from post content."""
    platforms: dict[str, dict[str, int]] = {}
    for record in chat_log:
        if record.action_type not in ("create_post", "CREATE_POST"):
            continue
        platform = record.platform.capitalize()
        if platform not in platforms:
            platforms[platform] = {"positive": 0, "negative": 0}
        text = str(record.action_args.get("text", "")).lower()
        for word in text.split():
            word = word.strip(".,!?;:")
            if word in POSITIVE_WORDS:
                platforms[platform]["positive"] += 1
            elif word in NEGATIVE_WORDS:
                platforms[platform]["negative"] += 1

    result = []
    for platform, counts in platforms.items():
        total = counts["positive"] + counts["negative"]
        if total == 0:
            result.append({"label": platform, "value": 50, "direction": "positive"})
        else:
            pct = int(counts["positive"] / total * 100)
            direction = "positive" if pct >= 50 else "negative"
            result.append({"label": platform, "value": pct, "direction": direction})
    return result


def _detect_coalitions(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Detect agent coalitions from interaction patterns."""
    interaction_pairs: dict[tuple[str, str], int] = {}
    for record in chat_log:
        if record.action_type in ("vote", "LIKE_POST", "reply", "repost", "REPOST"):
            target = record.action_args.get("post_id") or record.action_args.get("agent_id")
            if target:
                key = tuple(sorted([record.agent_name, str(target)]))
                interaction_pairs[key] = interaction_pairs.get(key, 0) + 1

    # Group agents with mutual interactions
    agents_in_coalitions: set[str] = set()
    coalition_groups: list[set[str]] = []
    for (a, b), count in sorted(interaction_pairs.items(), key=lambda x: -x[1]):
        if count < 2:
            continue
        placed = False
        for group in coalition_groups:
            if a in group or b in group:
                group.add(a)
                group.add(b)
                placed = True
                break
        if not placed:
            coalition_groups.append({a, b})

    colors = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7"]
    result = []
    for i, group in enumerate(coalition_groups[:4]):
        result.append({
            "name": f"Coalition {i + 1}",
            "description": f"Members: {', '.join(sorted(group))}",
            "agents": len(group),
            "strength": min(100, len(group) * 20),
            "color": colors[i % len(colors)],
        })
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/adapter.py tests/engine/test_adapter.py
git commit -m "feat: add output adapter for MiroShark-compatible JSON"
```

---

### Task 3: Rich Sim Data Extractor

Extracts posts, trades, trajectories, engagement data from the engine's in-memory state (replaces MiroShark's SQLite-based extraction).

**Files:**
- Create: `simswarm/extractor.py`
- Create: `tests/engine/test_extractor.py`

- [ ] **Step 1: Write extractor tests**

```python
# tests/engine/test_extractor.py
"""Test rich sim data extraction from engine state."""
from __future__ import annotations

from simswarm.extractor import (
    extract_posts,
    extract_engagement_summary,
    extract_agent_trajectories,
    extract_social_graph,
)
from simswarm.types import ActionRecord


SAMPLE_LOG = [
    ActionRecord(round_num=1, agent_id="e1", agent_name="Alice",
                 action_type="create_post", platform="social",
                 action_args={"text": "Markets look strong today"}, success=True),
    ActionRecord(round_num=1, agent_id="e2", agent_name="Bob",
                 action_type="create_post", platform="social",
                 action_args={"text": "I see a crisis coming"}, success=True),
    ActionRecord(round_num=2, agent_id="e1", agent_name="Alice",
                 action_type="vote", platform="social",
                 action_args={"post_id": "p1", "value": 1}, success=True),
    ActionRecord(round_num=2, agent_id="e2", agent_name="Bob",
                 action_type="follow", platform="social",
                 action_args={"agent_id": "e1"}, success=True),
    ActionRecord(round_num=3, agent_id="e1", agent_name="Alice",
                 action_type="create_post", platform="social",
                 action_args={"text": "Recovery is underway"}, success=True),
    ActionRecord(round_num=3, agent_id="e2", agent_name="Bob",
                 action_type="do_nothing", platform="social", action_args={}, success=True),
]


class TestExtractPosts:
    def test_returns_only_post_actions(self):
        posts = extract_posts(SAMPLE_LOG)
        assert len(posts) == 3
        for p in posts:
            assert "content" in p
            assert "agent_name" in p

    def test_includes_round_num(self):
        posts = extract_posts(SAMPLE_LOG)
        assert posts[0]["round_num"] == 1


class TestExtractEngagement:
    def test_returns_per_round_summary(self):
        summary = extract_engagement_summary(SAMPLE_LOG)
        assert len(summary) >= 1
        for entry in summary:
            assert "round" in entry
            assert "total_posts" in entry
            assert "active_agents" in entry

    def test_round_1_has_two_posts(self):
        summary = extract_engagement_summary(SAMPLE_LOG)
        r1 = next(s for s in summary if s["round"] == 1)
        assert r1["total_posts"] == 2


class TestExtractTrajectories:
    def test_returns_per_agent_data(self):
        trajectories = extract_agent_trajectories(SAMPLE_LOG)
        assert len(trajectories) == 2
        names = {t["name"] for t in trajectories}
        assert names == {"Alice", "Bob"}

    def test_includes_post_counts(self):
        trajectories = extract_agent_trajectories(SAMPLE_LOG)
        alice = next(t for t in trajectories if t["name"] == "Alice")
        total_posts = sum(r["posts"] for r in alice["rounds"])
        assert total_posts == 2


class TestExtractSocialGraph:
    def test_detects_follow_edges(self):
        graph = extract_social_graph(SAMPLE_LOG)
        assert len(graph["edges"]) >= 1
        edge = graph["edges"][0]
        assert "follower_name" in edge
        assert "followee_id" in edge
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_extractor.py -v`
Expected: FAIL

- [ ] **Step 3: Write the extractor**

```python
# simswarm/extractor.py
"""Rich simulation data extractor.

Extracts posts, engagement, trajectories, and social graph from
the engine's ActionRecord log. Replaces MiroShark's SQLite-based extraction.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from simswarm.types import ActionRecord

POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success",
    "positive", "progress", "growth", "improve", "achieve", "gain",
    "strong", "stable", "recovery", "profit", "optimistic",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "conflict", "damage", "destroy", "negative",
    "decline", "loss", "risk", "recession", "collapse",
}


def extract_posts(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Extract all post-creation actions as post records."""
    posts = []
    for record in chat_log:
        if record.action_type in ("create_post", "CREATE_POST"):
            posts.append({
                "agent_id": record.agent_id,
                "agent_name": record.agent_name,
                "platform": record.platform,
                "content": record.action_args.get("text", ""),
                "round_num": record.round_num,
                "timestamp": record.timestamp,
            })
    return posts


def extract_engagement_summary(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Compute per-round engagement metrics."""
    rounds: dict[int, dict[str, Any]] = {}
    for record in chat_log:
        r = record.round_num
        if r not in rounds:
            rounds[r] = {"posts": 0, "likes": 0, "comments": 0, "agents": set()}
        rounds[r]["agents"].add(record.agent_id)
        if record.action_type in ("create_post", "CREATE_POST"):
            rounds[r]["posts"] += 1
        elif record.action_type in ("vote", "LIKE_POST", "LIKE_COMMENT"):
            rounds[r]["likes"] += 1
        elif record.action_type in ("reply", "CREATE_COMMENT"):
            rounds[r]["comments"] += 1

    result = []
    for r in sorted(rounds.keys()):
        data = rounds[r]
        result.append({
            "round": r,
            "total_posts": data["posts"],
            "total_likes": data["likes"],
            "total_comments": data["comments"],
            "active_agents": len(data["agents"]),
        })
    return result


def extract_agent_trajectories(
    chat_log: list[ActionRecord],
) -> list[dict[str, Any]]:
    """Compute per-agent activity and sentiment over rounds."""
    agent_rounds: dict[str, dict[str, Any]] = {}
    for record in chat_log:
        key = record.agent_id
        if key not in agent_rounds:
            agent_rounds[key] = {"name": record.agent_name, "data": defaultdict(lambda: {"posts": 0, "actions": 0, "text": []})}
        rd = agent_rounds[key]["data"][record.round_num]
        rd["actions"] += 1
        if record.action_type in ("create_post", "CREATE_POST"):
            rd["posts"] += 1
            rd["text"].append(record.action_args.get("text", ""))

    result = []
    for agent_id, info in agent_rounds.items():
        rounds = []
        for r in sorted(info["data"].keys()):
            rd = info["data"][r]
            sentiment = _score_sentiment(" ".join(rd["text"])) if rd["text"] else 0.0
            rounds.append({
                "round": r,
                "posts": rd["posts"],
                "actions": rd["actions"],
                "sentiment": sentiment,
            })
        result.append({
            "agent_id": agent_id,
            "name": info["name"],
            "rounds": rounds,
        })
    return result


def extract_social_graph(chat_log: list[ActionRecord]) -> dict[str, Any]:
    """Extract follow relationships from the chat log."""
    edges = []
    mutual_pairs = []
    follows: dict[str, set[str]] = {}

    for record in chat_log:
        if record.action_type in ("follow", "FOLLOW"):
            target_id = record.action_args.get("agent_id", "")
            if target_id:
                edges.append({
                    "follower_id": record.agent_id,
                    "follower_name": record.agent_name,
                    "followee_id": target_id,
                    "followee_name": target_id,  # name may not be available
                    "platform": record.platform,
                })
                if record.agent_id not in follows:
                    follows[record.agent_id] = set()
                follows[record.agent_id].add(target_id)

    # Detect mutual follows
    seen = set()
    for a, targets in follows.items():
        for b in targets:
            if b in follows and a in follows[b]:
                pair = tuple(sorted([a, b]))
                if pair not in seen:
                    seen.add(pair)
                    mutual_pairs.append({"agent_a": pair[0], "agent_b": pair[1]})

    return {"edges": edges, "mutual_follows": mutual_pairs}


def extract_market_data(chat_log: list[ActionRecord]) -> list[dict[str, Any]]:
    """Extract trade records from market actions."""
    trades = []
    for record in chat_log:
        if record.action_type in ("buy_shares", "sell_shares"):
            trades.append({
                "agent_id": record.agent_id,
                "agent_name": record.agent_name,
                "side": "buy" if "buy" in record.action_type else "sell",
                "market_id": record.action_args.get("market_id", ""),
                "outcome": record.action_args.get("outcome", ""),
                "amount": record.action_args.get("amount", 0),
                "round": record.round_num,
            })
    return trades


def _score_sentiment(text: str) -> float:
    """Simple keyword-based sentiment scoring."""
    words = text.lower().split()
    pos = sum(1 for w in words if w.strip(".,!?;:") in POSITIVE_WORDS)
    neg = sum(1 for w in words if w.strip(".,!?;:") in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/extractor.py tests/engine/test_extractor.py
git commit -m "feat: add rich sim data extractor from engine state"
```

---

### Task 4: Report Module

Lean report generator with tool access over SimulationResult. Uses the smart LLM client for multi-turn report writing.

**Files:**
- Create: `simswarm/report.py`
- Create: `simswarm/prompts/report.j2`
- Create: `tests/engine/test_report.py`

- [ ] **Step 1: Write report module tests**

```python
# tests/engine/test_report.py
"""Test report module: tool dispatch, report generation, output shape."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from simswarm.llm import LLMClient, LLMResponse
from simswarm.report import ReportGenerator, ReportTools
from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult, SimulationState


def _make_result() -> SimulationResult:
    return SimulationResult(
        chat_log=[
            ActionRecord(round_num=1, agent_id="e1", agent_name="Alice",
                         action_type="create_post", platform="social",
                         action_args={"text": "Markets are strong"}, success=True),
            ActionRecord(round_num=2, agent_id="e2", agent_name="Bob",
                         action_type="create_post", platform="social",
                         action_args={"text": "I see a crisis"}, success=True),
            ActionRecord(round_num=3, agent_id="e1", agent_name="Alice",
                         action_type="vote", platform="social",
                         action_args={"post_id": "p1", "value": 1}, success=True),
        ],
        graph_data=GraphSnapshot(
            nodes=[
                {"uuid": "n1", "name": "Alice", "labels": ["Person"], "summary": "Analyst"},
                {"uuid": "n2", "name": "Bob", "labels": ["Person"], "summary": "Reporter"},
            ],
            edges=[{"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2",
                    "name": "interacts_with", "fact": "Interact"}],
            metadata={"entity_types": ["Person"], "total_nodes": 2, "total_edges": 1},
        ),
        trajectories={},
        market_data=None,
        raw_state=None,
    )


class TestReportTools:
    def test_get_top_posts_returns_posts(self):
        result = _make_result()
        tools = ReportTools(result)
        posts = tools.get_top_posts(limit=5)
        assert len(posts) >= 1
        assert "content" in posts[0]

    def test_get_coalitions_returns_list(self):
        result = _make_result()
        tools = ReportTools(result)
        coalitions = tools.get_coalitions()
        assert isinstance(coalitions, list)

    def test_get_agent_summary_returns_dict(self):
        result = _make_result()
        tools = ReportTools(result)
        summary = tools.get_agent_summary("e1")
        assert summary["name"] == "Alice"
        assert "total_actions" in summary

    def test_get_agent_summary_unknown_agent(self):
        result = _make_result()
        tools = ReportTools(result)
        summary = tools.get_agent_summary("unknown")
        assert summary["name"] == "unknown"


class TestReportGenerator:
    @pytest.mark.asyncio
    async def test_generate_returns_markdown(self):
        mock_llm = AsyncMock(spec=LLMClient)
        # First call: LLM uses get_top_posts tool
        # Second call: LLM returns report text
        mock_llm.chat.side_effect = [
            LLMResponse(content="", tool_calls=[
                {"name": "get_top_posts", "args": {"limit": 5}},
            ], raw={}),
            LLMResponse(
                content="# Simulation Report\n\n## Executive Summary\n\nMarkets show mixed signals.\n\n## Key Findings\n\n- Alice is bullish\n- Bob is bearish\n\n## Coalitions\n\nNo clear coalitions formed.",
                tool_calls=[],
                raw={},
            ),
        ]
        gen = ReportGenerator(mock_llm)
        result = _make_result()
        report = await gen.generate(result, goal="Predict market sentiment")
        assert "# Simulation Report" in report.raw_markdown
        assert len(report.raw_markdown) > 50

    @pytest.mark.asyncio
    async def test_generate_extracts_brief(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="# Report\n\n## Executive Summary\n\nThe market is volatile.\n\n## Findings\n\n- Finding 1",
            tool_calls=[],
            raw={},
        )
        gen = ReportGenerator(mock_llm)
        result = _make_result()
        report = await gen.generate(result, goal="Test")
        assert len(report.executive_brief) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_report.py -v`
Expected: FAIL

- [ ] **Step 3: Write the report Jinja2 template**

```jinja2
{# simswarm/prompts/report.j2 #}
You are the SimSwarm Report Agent. Your job is to analyze simulation results and write a comprehensive report.

Simulation goal: {{ goal }}

You have access to tools that query the simulation data. Use them to gather evidence before writing.

Available data:
- {{ agent_count }} agents participated over {{ round_count }} rounds
- {{ post_count }} posts were created
- {{ entity_count }} entities in the knowledge graph

Write a report with these sections:
1. **Executive Summary** — 2-3 sentence overview
2. **Key Findings** — bullet points with evidence from the simulation
3. **Agent Coalitions** — groups that formed and their dynamics
4. **Market Analysis** — if prediction market data exists
5. **Conclusion** — synthesis and confidence assessment

Use markdown formatting. Be specific — cite agent names, round numbers, and data points.
```

- [ ] **Step 4: Write the report module**

```python
# simswarm/report.py
"""Report generation module.

Lean replacement for MiroShark's 3,200-line ReportAgent.
Multi-turn LLM with tool access over SimulationResult.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from simswarm.extractor import extract_posts, extract_agent_trajectories
from simswarm.llm import LLMClient
from simswarm.types import ActionRecord, SimulationResult

TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), keep_trailing_newline=False)


@dataclass
class Report:
    """Structured report output."""
    executive_brief: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)
    raw_markdown: str = ""


class ReportTools:
    """Query tools over simulation results — called by the report LLM."""

    def __init__(self, result: SimulationResult):
        self.result = result
        self._posts = extract_posts(result.chat_log)
        self._trajectories = extract_agent_trajectories(result.chat_log)

    def get_top_posts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most notable posts (by round order for now)."""
        return self._posts[:limit]

    def get_coalitions(self) -> list[dict[str, Any]]:
        """Detect agent coalitions from interaction patterns."""
        from simswarm.adapter import _detect_coalitions
        return _detect_coalitions(self.result.chat_log)

    def get_agent_summary(self, agent_id: str) -> dict[str, Any]:
        """Summarize one agent's journey through the simulation."""
        actions = [r for r in self.result.chat_log if r.agent_id == agent_id]
        name = actions[0].agent_name if actions else agent_id
        posts = [a for a in actions if a.action_type in ("create_post", "CREATE_POST")]
        return {
            "name": name,
            "total_actions": len(actions),
            "total_posts": len(posts),
            "rounds_active": len({a.round_num for a in actions}),
            "sample_posts": [p.action_args.get("text", "")[:200] for p in posts[:3]],
        }

    def get_trajectory(self, agent_id: str) -> list[dict[str, Any]]:
        """Get per-round trajectory for an agent."""
        for t in self._trajectories:
            if t["agent_id"] == agent_id:
                return t["rounds"]
        return []

    def dispatch(self, tool_name: str, args: dict) -> str:
        """Dispatch a tool call and return JSON result."""
        handler = {
            "get_top_posts": lambda a: self.get_top_posts(a.get("limit", 10)),
            "get_coalitions": lambda a: self.get_coalitions(),
            "get_agent_summary": lambda a: self.get_agent_summary(a.get("agent_id", "")),
            "get_trajectory": lambda a: self.get_trajectory(a.get("agent_id", "")),
        }.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return json.dumps(handler(args), default=str)

    @staticmethod
    def tool_schemas() -> list[dict]:
        """OpenAI function-calling tool schemas for report tools."""
        return [
            {"type": "function", "function": {
                "name": "get_top_posts",
                "description": "Get the most notable posts from the simulation",
                "parameters": {"type": "object", "properties": {
                    "limit": {"type": "integer", "description": "Max posts to return"},
                }, "required": []},
            }},
            {"type": "function", "function": {
                "name": "get_coalitions",
                "description": "Detect agent coalitions from interaction patterns",
                "parameters": {"type": "object", "properties": {}},
            }},
            {"type": "function", "function": {
                "name": "get_agent_summary",
                "description": "Get summary of one agent's behavior",
                "parameters": {"type": "object", "properties": {
                    "agent_id": {"type": "string"},
                }, "required": ["agent_id"]},
            }},
            {"type": "function", "function": {
                "name": "get_trajectory",
                "description": "Get per-round activity trajectory for an agent",
                "parameters": {"type": "object", "properties": {
                    "agent_id": {"type": "string"},
                }, "required": ["agent_id"]},
            }},
        ]


class ReportGenerator:
    """Multi-turn report generator using LLM with tool access."""

    MAX_TOOL_ROUNDS = 5

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate(self, result: SimulationResult, goal: str) -> Report:
        """Generate a report from simulation results."""
        tools = ReportTools(result)
        posts = extract_posts(result.chat_log)

        # Build system prompt
        template = _jinja.get_template("report.j2")
        system_prompt = template.render(
            goal=goal,
            agent_count=len({r.agent_name for r in result.chat_log}),
            round_count=max((r.round_num for r in result.chat_log), default=0),
            post_count=len(posts),
            entity_count=len(result.graph_data.nodes),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Analyze the simulation data using the available tools, then write the report."},
        ]

        # Multi-turn: LLM can call tools, then we feed results back
        for _ in range(self.MAX_TOOL_ROUNDS):
            response = await self.llm.chat(
                messages,
                tools=ReportTools.tool_schemas(),
                temperature=0.3,
            )
            if not response.tool_calls:
                # LLM produced final text
                break

            # Execute tool calls and feed results back
            for call in response.tool_calls:
                tool_result = tools.dispatch(call["name"], call["args"])
                messages.append({"role": "assistant", "content": f"Called {call['name']}"})
                messages.append({"role": "user", "content": f"Tool result for {call['name']}:\n{tool_result}"})
        else:
            # Exceeded tool rounds, ask for final output
            messages.append({"role": "user", "content": "Please write the final report now."})
            response = await self.llm.chat(messages, temperature=0.3)

        markdown = response.content
        brief = _extract_brief(markdown)
        findings = _extract_findings(markdown)

        return Report(
            executive_brief=brief,
            findings=findings,
            raw_markdown=markdown,
        )


def _extract_brief(markdown: str) -> str:
    """Extract executive summary from markdown report."""
    lines = markdown.split("\n")
    in_summary = False
    brief_lines = []
    for line in lines:
        if "executive summary" in line.lower() or "summary" in line.lower() and line.startswith("#"):
            in_summary = True
            continue
        if in_summary and line.startswith("#"):
            break
        if in_summary and line.strip():
            brief_lines.append(line.strip())
    return " ".join(brief_lines) if brief_lines else markdown[:200]


def _extract_findings(markdown: str) -> list[dict[str, str]]:
    """Extract key findings as structured list."""
    lines = markdown.split("\n")
    findings = []
    in_findings = False
    for line in lines:
        if "finding" in line.lower() and line.startswith("#"):
            in_findings = True
            continue
        if in_findings and line.startswith("#"):
            break
        if in_findings and line.strip().startswith("- "):
            text = line.strip()[2:]
            findings.append({"title": text[:80], "description": text})
    return findings
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_report.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add simswarm/report.py simswarm/prompts/report.j2 tests/engine/test_report.py
git commit -m "feat: add lean report generator with tool access"
```

---

### Task 5: New run_job_v2.py

The new pipeline entry point. Uses graph_ops.py (unchanged, still MiroShark) for entity extraction, then runs the SimSwarm engine for simulation, and writes output in the compatible format.

**Files:**
- Create: `infra/docker/run_job_v2.py`
- Create: `tests/engine/test_run_job_v2.py`

- [ ] **Step 1: Write run_job_v2 tests**

```python
# tests/engine/test_run_job_v2.py
"""Test the new pipeline: config assembly, result writing, output format."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from simswarm.llm import LLMClient, LLMResponse
from tests.contracts.schemas import ChatLogEntry, GraphData, StructuredResults


# We test the pure-Python helpers, not the full pipeline (which needs Neo4j)

# Import helpers from run_job_v2 via importlib to avoid Neo4j imports at module level
import importlib.util
import sys

RUN_JOB_V2_PATH = Path(__file__).resolve().parent.parent.parent / "infra" / "docker" / "run_job_v2.py"


@pytest.fixture(scope="module")
def run_job_mod():
    """Load run_job_v2 module, stubbing out graph_ops and Neo4j imports."""
    # Create mock modules
    mock_graph_ops = MagicMock()
    mock_graph_ops.build_graph.return_value = ("project-1", "graph-1")
    sys.modules["graph_ops"] = mock_graph_ops

    mock_simulation = MagicMock()
    sys.modules["simulation"] = mock_simulation

    mock_service_init = MagicMock()
    sys.modules["service_init"] = mock_service_init

    mock_constants = MagicMock()
    mock_constants.VLLM_URL = "http://localhost:8000/v1"
    sys.modules.setdefault("constants", mock_constants)

    spec = importlib.util.spec_from_file_location("run_job_v2", RUN_JOB_V2_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod

    # Cleanup
    for name in ["graph_ops", "simulation", "service_init"]:
        sys.modules.pop(name, None)


class TestWriteResults:
    def test_write_results_creates_all_files(self, run_job_mod, tmp_path):
        """Verify write_results creates the expected output files."""
        from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult
        from simswarm.report import Report

        result = SimulationResult(
            chat_log=[
                ActionRecord(round_num=1, agent_id="e1", agent_name="Alice",
                             action_type="create_post", platform="social",
                             action_args={"text": "Hello"}, success=True),
            ],
            graph_data=GraphSnapshot(
                nodes=[{"uuid": "n1", "name": "Alice", "labels": ["Person"], "summary": "Test"}],
                edges=[],
                metadata={"entity_types": ["Person"], "total_nodes": 1, "total_edges": 0},
            ),
            trajectories={},
            market_data=None,
            raw_state=None,
        )
        report = Report(
            executive_brief="Test brief.",
            findings=[{"title": "F1", "description": "Finding 1"}],
            raw_markdown="# Report\n\n## Executive Summary\n\nTest brief.",
        )

        run_job_mod.write_results(result, report, str(tmp_path))

        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "chat_log.json").exists()
        assert (tmp_path / "graph_data.json").exists()
        assert (tmp_path / "structured_results.json").exists()

    def test_chat_log_validates_against_contract(self, run_job_mod, tmp_path):
        from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult
        from simswarm.report import Report

        result = SimulationResult(
            chat_log=[
                ActionRecord(round_num=1, agent_id="e1", agent_name="Alice",
                             action_type="CREATE_POST", platform="social",
                             action_args={"text": "Post"}, success=True),
            ],
            graph_data=GraphSnapshot(nodes=[], edges=[], metadata={"entity_types": [], "total_nodes": 0, "total_edges": 0}),
            trajectories={}, market_data=None, raw_state=None,
        )
        report = Report(executive_brief="Brief.", findings=[], raw_markdown="# Report")

        run_job_mod.write_results(result, report, str(tmp_path))

        chat_log = json.loads((tmp_path / "chat_log.json").read_text())
        for entry in chat_log:
            ChatLogEntry.model_validate(entry)

    def test_structured_results_validates_against_contract(self, run_job_mod, tmp_path):
        from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult
        from simswarm.report import Report

        result = SimulationResult(
            chat_log=[
                ActionRecord(round_num=1, agent_id="e1", agent_name="Alice",
                             action_type="create_post", platform="social",
                             action_args={"text": "Test"}, success=True),
            ],
            graph_data=GraphSnapshot(
                nodes=[{"uuid": "n1", "name": "X", "labels": ["E"], "summary": "s"}],
                edges=[], metadata={"entity_types": ["E"], "total_nodes": 1, "total_edges": 0},
            ),
            trajectories={}, market_data=None, raw_state=None,
        )
        report = Report(
            executive_brief="Brief.",
            findings=[{"title": "F1", "description": "Desc"}],
            raw_markdown="# R",
        )

        run_job_mod.write_results(result, report, str(tmp_path))

        structured = json.loads((tmp_path / "structured_results.json").read_text())
        StructuredResults.model_validate(structured)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_run_job_v2.py -v`
Expected: FAIL

- [ ] **Step 3: Write run_job_v2.py**

```python
#!/usr/bin/env python3
"""SimSwarm engine pipeline — replaces MiroShark simulation step.

Graph building still uses MiroShark (OntologyGenerator, TextProcessor).
Simulation uses the new SimSwarm engine.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Add paths
DOCKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCKER_DIR))
sys.path.insert(0, str(DOCKER_DIR.parent.parent))  # repo root for simswarm package


def write_results(
    result: "SimulationResult",
    report: "Report",
    output_dir: str,
) -> None:
    """Write simulation results to output directory in MiroShark-compatible format."""
    from simswarm.adapter import adapt_chat_log, adapt_graph_data, adapt_structured
    from simswarm.extractor import (
        extract_posts,
        extract_engagement_summary,
        extract_agent_trajectories,
        extract_social_graph,
        extract_market_data,
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Core result files (contract with worker_api.py)
    (out / "report.md").write_text(report.raw_markdown)

    chat_log = adapt_chat_log(result.chat_log)
    (out / "chat_log.json").write_text(json.dumps(chat_log, ensure_ascii=False, default=str))

    graph_data = adapt_graph_data(result.graph_data)
    (out / "graph_data.json").write_text(json.dumps(graph_data, ensure_ascii=False, default=str))

    structured = adapt_structured(
        brief=report.executive_brief,
        findings=report.findings,
        chat_log=result.chat_log,
        graph_data=result.graph_data,
    )
    (out / "structured_results.json").write_text(json.dumps(structured, ensure_ascii=False, default=str))

    # Rich sim data files
    posts = extract_posts(result.chat_log)
    (out / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, default=str))

    engagement = extract_engagement_summary(result.chat_log)
    (out / "engagement_summary.json").write_text(json.dumps(engagement, ensure_ascii=False, default=str))

    trajectories = extract_agent_trajectories(result.chat_log)
    (out / "agent_trajectories.json").write_text(json.dumps(trajectories, ensure_ascii=False, default=str))

    social_graph = extract_social_graph(result.chat_log)
    (out / "social_graph.json").write_text(json.dumps(social_graph, ensure_ascii=False, default=str))

    trades = extract_market_data(result.chat_log)
    (out / "trades.json").write_text(json.dumps(trades, ensure_ascii=False, default=str))

    # Summary
    summary = {
        "status": "completed",
        "engine": "simswarm",
        "report_length": len(report.raw_markdown),
        "chat_log_entries": len(chat_log),
        "graph_nodes": len(graph_data.get("nodes", [])),
        "graph_edges": len(graph_data.get("edges", [])),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False))


async def run_simulation(
    seed_text: str,
    goal: str,
    max_rounds: int,
    entities: list[dict[str, Any]],
    target_agents: int = 5,
) -> "SimulationResult":
    """Run the SimSwarm engine with the given entities."""
    from simswarm.engine import Engine
    from simswarm.llm import LLMClient
    from simswarm.types import (
        EngineConfig,
        Entity,
        EnvironmentConfig,
        SimulationConfig,
    )

    vllm_url = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
    model_name = os.environ.get("LLM_MODEL_NAME", "default")
    api_key = os.environ.get("LLM_API_KEY", "none")
    smart_url = os.environ.get("SMART_LLM_URL", vllm_url)
    smart_model = os.environ.get("SMART_LLM_MODEL", model_name)

    fast_llm = LLMClient(base_url=vllm_url, model=model_name, api_key=api_key)
    smart_llm = LLMClient(base_url=smart_url, model=smart_model, api_key=api_key)

    engine = Engine(
        fast_llm=fast_llm,
        smart_llm=smart_llm,
        engine_config=EngineConfig(concurrency=32),
    )

    sim_entities = [
        Entity(
            id=e.get("uuid", e.get("id", "")),
            name=e.get("name", ""),
            type=e.get("type", e.get("labels", ["unknown"])[0] if e.get("labels") else "unknown"),
            summary=e.get("summary", ""),
        )
        for e in entities
    ]

    config = SimulationConfig(
        seed_text=seed_text,
        goal=goal,
        entities=sim_entities[:target_agents],
        environments=[
            EnvironmentConfig(type="social", params={}),
            EnvironmentConfig(type="market", params={
                "markets": [{"question": f"Will the outcome of '{goal[:60]}' be positive?",
                             "initial_price_yes": 0.5}],
                "initial_balance": 1000.0,
            }),
        ],
        rounds=max_rounds,
        concurrency=32,
    )

    logger.info(f"Starting SimSwarm engine: {len(sim_entities)} agents, {max_rounds} rounds")
    result = await engine.run(config)
    logger.info(f"Simulation complete: {len(result.chat_log)} actions logged")

    await fast_llm.close()
    await smart_llm.close()

    return result


def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
) -> dict:
    """Full pipeline: build graph → run SimSwarm engine → generate report → write results."""
    from simswarm.report import ReportGenerator
    from simswarm.llm import LLMClient

    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Build knowledge graph (still uses MiroShark graph tools)
    logger.info("Step 1/4: Building knowledge graph...")
    try:
        from graph_ops import build_graph
        from service_init import wait_for_neo4j
        wait_for_neo4j()
        storage = _get_neo4j_storage()
        project_id, graph_id = build_graph(seed_text, goal, storage)
        entities = _extract_entities(graph_id, storage)
        logger.info(f"Graph built: {len(entities)} entities")
    except ImportError:
        logger.warning("graph_ops not available — using seed text for entity extraction")
        entities = _fallback_entities(seed_text, target_agents)
        graph_id = "fallback"

    # Step 2: Run simulation
    logger.info("Step 2/4: Running simulation...")
    result = asyncio.run(run_simulation(
        seed_text=seed_text,
        goal=goal,
        max_rounds=max_rounds,
        entities=entities,
        target_agents=target_agents,
    ))

    # Step 3: Generate report
    logger.info("Step 3/4: Generating report...")
    smart_url = os.environ.get("SMART_LLM_URL", os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1"))
    smart_model = os.environ.get("SMART_LLM_MODEL", os.environ.get("LLM_MODEL_NAME", "default"))
    api_key = os.environ.get("LLM_API_KEY", "none")
    smart_llm = LLMClient(base_url=smart_url, model=smart_model, api_key=api_key)
    report_gen = ReportGenerator(smart_llm)
    report = asyncio.run(report_gen.generate(result, goal=goal))
    asyncio.run(smart_llm.close())

    # Step 4: Write results
    logger.info("Step 4/4: Writing results...")
    write_results(result, report, output_dir)

    elapsed = time.time() - start
    logger.info(f"Pipeline complete in {elapsed:.0f}s")

    return {
        "status": "completed",
        "engine": "simswarm",
        "graph_id": graph_id,
        "report_length": len(report.raw_markdown),
        "chat_log_entries": len(result.chat_log),
        "graph_nodes": len(result.graph_data.nodes),
        "graph_edges": len(result.graph_data.edges),
    }


def _get_neo4j_storage():
    """Get Neo4j storage instance."""
    from app.storage.neo4j_storage import Neo4jStorage
    return Neo4jStorage()


def _extract_entities(graph_id: str, storage) -> list[dict]:
    """Extract entities from Neo4j graph as dicts."""
    data = storage.get_graph_data(graph_id)
    return data.get("nodes", [])


def _fallback_entities(seed_text: str, count: int) -> list[dict]:
    """Extract simple entities from seed text when Neo4j is unavailable."""
    words = seed_text.split()
    capitalized = [w.strip(".,!?;:") for w in words if w[0:1].isupper() and len(w) > 2]
    unique = list(dict.fromkeys(capitalized))[:count]
    return [
        {"uuid": f"e{i}", "name": name, "labels": ["Entity"], "summary": f"Entity from seed: {name}"}
        for i, name in enumerate(unique)
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SimSwarm pipeline")
    parser.add_argument("--seed-text", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--output-dir", default="/tmp/results")
    parser.add_argument("--target-agents", type=int, default=5)
    args = parser.parse_args()

    result = run_pipeline(
        seed_text=args.seed_text,
        goal=args.goal,
        max_rounds=args.max_rounds,
        output_dir=args.output_dir,
        target_agents=args.target_agents,
    )
    print(json.dumps(result, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_run_job_v2.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add infra/docker/run_job_v2.py tests/engine/test_run_job_v2.py
git commit -m "feat: add SimSwarm pipeline entry point (run_job_v2)"
```

---

### Task 6: Full Stack Verification

Run all tests together — contracts, engine unit tests, and integration.

**Files:**
- No new files — verification only.

- [ ] **Step 1: Run the full test suite**

```bash
pytest tests/contracts/ tests/engine/ -v --tb=short
```

Expected: All pass (golden file tests skip).

- [ ] **Step 2: Count total tests and coverage**

```bash
pytest tests/contracts/ tests/engine/ -v --tb=short 2>&1 | tail -5
```

- [ ] **Step 3: Commit any fixes if needed**

---

## Run All Tests

After completing all tasks:

```bash
# Phase 1: Contract tests
pytest tests/contracts/ -v

# Phase 2+3: Engine tests
pytest tests/engine/ -v

# Everything
pytest tests/contracts/ tests/engine/ -v
```
