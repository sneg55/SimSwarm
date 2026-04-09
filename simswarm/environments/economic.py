"""Economic environment: firms, labor, pricing, investment, and policy shocks.

Agents represent economic actors (producers, governments, consumers) with actions
like hire, invest, and set_price. Aggregate metrics update via rule-based formulas
each tick. Significant metric shifts publish events to the bridge.
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
    agent_id: str
    role: str
    balance: float
    workforce: int = 0
    price: float = 0.0
    output: float = 0.0


class EconomicEnvironment:
    """Rule-based economic simulation environment."""

    name = "economic"

    def __init__(self, config: EconomicConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.actors: dict[str, EconomicActor] = {}
        self.active_policies: list[dict[str, Any]] = []
        self.scenario_variables: dict[str, Any] = {}
        self.metrics: dict[str, float] = {
            "employment_rate": 0.0,
            "avg_price": 0.0,
            "total_output": 0.0,
            "total_investment": 0.0,
        }
        self._pending_events: list[Event] = []
        self._last_metrics: dict[str, float] = dict(self.metrics)
        self._total_investment_cumulative: float = 0.0

    def register_agent(self, agent: Agent, role: str = "producer", balance: float = 0.0) -> None:
        if agent.id not in self.actors:
            self.actors[agent.id] = EconomicActor(
                agent_id=agent.id, role=role, balance=balance,
            )

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
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

    def tick(self) -> None:
        self.current_round += 1
        self._last_metrics = dict(self.metrics)
        self._compute_metrics()
        self._emit_metric_change_events()

    def get_observations(self, agent: Agent) -> Observation:
        self.register_agent(agent)
        lines = ["=== Economic State ==="]

        lines.append("Metrics:")
        for key, val in self.metrics.items():
            lines.append(f"  {key}: {val:.4f}")

        if self.active_policies:
            lines.append("Active policies:")
            for policy in self.active_policies:
                lines.append(f"  - {policy['name']}: {policy.get('description', '')}")

        if self.scenario_variables:
            lines.append("Scenario variables:")
            for k, v in self.scenario_variables.items():
                lines.append(f"  {k}: {v}")

        actor = self.actors.get(agent.id)
        if actor:
            lines.append(f"Your state: role={actor.role} balance={actor.balance} "
                         f"workforce={actor.workforce} price={actor.price} output={actor.output}")

        return Observation(environment=self.name, content="\n".join(lines))

    def get_tools(self) -> list[Tool]:
        return [
            Tool(name="set_price", description="Set the price for your goods or services",
                 parameters={"type": "object", "properties": {
                     "price": {"type": "number", "description": "New price to set"},
                 }, "required": ["price"]}),
            Tool(name="hire", description="Hire workers to increase your workforce",
                 parameters={"type": "object", "properties": {
                     "count": {"type": "integer", "description": "Number of workers to hire"},
                 }, "required": ["count"]}),
            Tool(name="fire", description="Lay off workers to reduce your workforce",
                 parameters={"type": "object", "properties": {
                     "count": {"type": "integer", "description": "Number of workers to lay off"},
                 }, "required": ["count"]}),
            Tool(name="invest", description="Invest capital to increase productive output",
                 parameters={"type": "object", "properties": {
                     "amount": {"type": "number", "description": "Amount of capital to invest"},
                 }, "required": ["amount"]}),
            Tool(name="allocate", description="Allocate funds to a target sector or program",
                 parameters={"type": "object", "properties": {
                     "target": {"type": "string", "description": "Allocation target"},
                     "amount": {"type": "number", "description": "Amount to allocate"},
                 }, "required": ["target", "amount"]}),
            Tool(name="apply_policy", description="Enact an economic policy",
                 parameters={"type": "object", "properties": {
                     "policy_name": {"type": "string", "description": "Short policy identifier"},
                     "description": {"type": "string", "description": "Policy description"},
                     "variable": {"type": "string", "description": "Optional scenario variable to set"},
                     "value": {"type": "number", "description": "Value for the scenario variable"},
                 }, "required": ["policy_name", "description"]}),
            Tool(name="do_nothing", description="Take no action this round",
                 parameters={"type": "object", "properties": {}}),
        ]

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_metrics(self) -> None:
        total_workforce = sum(a.workforce for a in self.actors.values())
        self.metrics["employment_rate"] = min(
            total_workforce / self.config.labor_force, 1.0
        ) if self.config.labor_force > 0 else 0.0

        prices = [a.price for a in self.actors.values() if a.price > 0]
        self.metrics["avg_price"] = sum(prices) / len(prices) if prices else 0.0

        self.metrics["total_output"] = sum(a.output for a in self.actors.values())
        self.metrics["total_investment"] = self._total_investment_cumulative

    def _emit_metric_change_events(self) -> None:
        threshold = self.config.metric_change_threshold
        for key, current in self.metrics.items():
            previous = self._last_metrics.get(key, 0.0)
            delta = abs(current - previous)
            if delta >= threshold:
                self._pending_events.append(Event(
                    source=self.name, type="metric_change",
                    data={"metric": key, "previous": previous,
                          "current": current, "delta": current - previous},
                    round=self.current_round,
                ))

    def _handle_set_price(self, agent: Agent, args: dict) -> ActionResult:
        price = args.get("price", 0.0)
        self.actors[agent.id].price = float(price)
        return ActionResult(success=True, data={"price": price})

    def _handle_hire(self, agent: Agent, args: dict) -> ActionResult:
        count = int(args.get("count", 0))
        self.actors[agent.id].workforce += count
        return ActionResult(success=True, data={"workforce": self.actors[agent.id].workforce})

    def _handle_fire(self, agent: Agent, args: dict) -> ActionResult:
        count = int(args.get("count", 0))
        actor = self.actors[agent.id]
        if count > actor.workforce:
            return ActionResult(success=False, data={
                "error": f"Cannot fire {count} workers, only {actor.workforce} employed"
            })
        actor.workforce -= count
        return ActionResult(success=True, data={"workforce": actor.workforce})

    def _handle_invest(self, agent: Agent, args: dict) -> ActionResult:
        amount = float(args.get("amount", 0.0))
        actor = self.actors[agent.id]
        if actor.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})
        actor.balance -= amount
        actor.output += amount
        self._total_investment_cumulative += amount
        return ActionResult(success=True, data={"invested": amount, "balance": actor.balance})

    def _handle_allocate(self, agent: Agent, args: dict) -> ActionResult:
        target = args.get("target", "")
        amount = float(args.get("amount", 0.0))
        return ActionResult(success=True, data={"target": target, "amount": amount})

    def _handle_apply_policy(self, agent: Agent, args: dict) -> ActionResult:
        policy_name = args.get("policy_name", "")
        description = args.get("description", "")
        variable = args.get("variable")
        value = args.get("value")
        policy: dict[str, Any] = {"name": policy_name, "description": description,
                                   "enacted_by": agent.id, "round": self.current_round}
        self.active_policies.append(policy)
        if variable is not None and value is not None:
            self.scenario_variables[variable] = value
        return ActionResult(success=True, data={"policy": policy_name})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})
