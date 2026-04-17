"""Core simulation engine: orchestrates rounds, agents, and environments."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from simswarm.belief import update_beliefs
from simswarm.bridge import Bridge
from simswarm.environments.social import SocialConfig, SocialEnvironment
from simswarm.environments.market import MarketConfig, MarketEnvironment
from simswarm.environments.economic import EconomicConfig, EconomicEnvironment
from simswarm.graph import build_graph
from simswarm.llm import LLMClient, build_context
from simswarm.stance import score_stance
from simswarm.sweep import ScenarioSweep, generate_sweep_configs
from simswarm.types import (
    Action,
    ActionRecord,
    Agent,
    AgentActivityConfig,
    BeliefState,
    EngineConfig,
    Entity,
    EnvironmentConfig,
    Observation,
    RoundSnapshot,
    SimulationConfig,
    SimulationResult,
    SimulationState,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, dict[str, Any]], Awaitable[None]]


class Engine:
    def __init__(
        self,
        fast_llm: LLMClient,
        smart_llm: LLMClient,
        engine_config: EngineConfig | None = None,
    ):
        self.fast_llm = fast_llm
        self.smart_llm = smart_llm
        self.config = engine_config or EngineConfig()

    async def run(
        self,
        config: SimulationConfig,
        on_progress: ProgressCallback | None = None,
    ) -> SimulationResult:
        environments = self._create_environments(config.environments)
        agents = self._create_agents(config.entities, list(environments.keys()))
        bridge = Bridge()
        chat_log: list[ActionRecord] = []
        snapshots: list[RoundSnapshot] = []
        semaphore = asyncio.Semaphore(config.concurrency)
        # Belief updates are driven by the sim's goal as a single topic. Names
        # for multi-topic support would be added here in a follow-up.
        belief_topic = (config.goal or "topic").strip()[:200] or "topic"

        for round_num in range(1, config.rounds + 1):
            bridge.inject_scheduled(config.scheduled_events, round_num)

            agent_observations: dict[str, list[Observation]] = {}
            for agent in agents.values():
                obs = []
                for env_name in agent.environments:
                    if env_name in environments:
                        obs.append(environments[env_name].get_observations(agent))
                digest = bridge.get_digest(agent)
                if digest:
                    obs.append(Observation(environment="bridge", content=digest))
                if config.variables:
                    var_lines = [f"  {k}: {v}" for k, v in config.variables.items()]
                    obs.append(Observation(
                        environment="scenario",
                        content="Current scenario variables:\n" + "\n".join(var_lines),
                    ))
                agent_observations[agent.id] = obs

            async def step_agent(agent: Agent) -> list[ActionRecord]:
                async with semaphore:
                    obs = agent_observations.get(agent.id, [])
                    tools = []
                    for env_name in agent.environments:
                        if env_name in environments:
                            tools.extend(environments[env_name].get_tools())
                    tool_schemas = [t.to_openai_schema() for t in tools]
                    messages = build_context(agent, obs)
                    response = await self.fast_llm.chat(messages, tools=tool_schemas)
                    records = []
                    for call in response.tool_calls:
                        action_name = call["name"]
                        action_args = call["args"]
                        target_env = self._find_env_for_action(action_name, environments, agent)
                        action = Action(
                            agent_id=agent.id, environment=target_env,
                            action_type=action_name, args=action_args,
                        )
                        if target_env in environments:
                            result = environments[target_env].execute_action(agent, action)
                        else:
                            result = None
                        records.append(ActionRecord(
                            round_num=round_num, agent_id=agent.id,
                            agent_name=agent.name, action_type=action_name,
                            platform=target_env, action_args=action_args,
                            success=result.success if result else False,
                            action_result=dict(result.data) if result and result.data else None,
                        ))
                        agent.memory.append(f"Round {round_num}: {action_name}({action_args})")
                        if len(agent.memory) > self.config.max_memory_rounds:
                            agent.memory = agent.memory[-self.config.max_memory_rounds:]
                    if not response.tool_calls:
                        records.append(ActionRecord(
                            round_num=round_num, agent_id=agent.id,
                            agent_name=agent.name, action_type="do_nothing",
                            platform=agent.environments[0] if agent.environments else "unknown",
                            action_args={},
                        ))
                    return records

            tasks = [step_agent(agent) for agent in agents.values()]
            results = await asyncio.gather(*tasks)
            round_records: list[ActionRecord] = []
            for records in results:
                chat_log.extend(records)
                round_records.extend(records)

            # Belief dynamics: each agent sees the posts authored by others this
            # round, weighted by stance. The old v1 (MiroShark) path ran this;
            # under v2 it had been stubbed out, leading to flat 0.0 sentiment.
            _apply_belief_updates(agents, round_records, belief_topic)

            for env in environments.values():
                env.tick()

            all_events = []
            for env in environments.values():
                all_events.extend(env.publish_events())
            bridge.receive_events(all_events)

            snapshots.append(RoundSnapshot(
                round=round_num,
                agent_count=len(agents),
                metrics={"actions": len([r for rs in results for r in rs])},
            ))

            if on_progress:
                await on_progress(round_num, config.rounds, snapshots[-1].metrics)

            bridge.clear()

        return SimulationResult(
            chat_log=chat_log,
            graph_data=build_graph(list(config.entities), chat_log),
            trajectories={},
            market_data=None,
            raw_state=SimulationState(
                round=config.rounds,
                agents=agents,
                environments=environments,
                events=[],
                snapshots=snapshots,
            ),
        )

    async def run_sweep(
        self,
        sweep: ScenarioSweep,
        on_progress: ProgressCallback | None = None,
    ) -> list[tuple[dict[str, Any], SimulationResult]]:
        configs = generate_sweep_configs(sweep)
        results = []
        for key, config in configs:
            result = await self.run(config, on_progress=on_progress)
            results.append((key, result))
        return results

    def _create_environments(self, env_configs: list[EnvironmentConfig]) -> dict[str, Any]:
        environments = {}
        for ec in env_configs:
            if ec.type == "social":
                environments["social"] = SocialEnvironment(SocialConfig(**ec.params))
            elif ec.type == "market":
                environments["market"] = MarketEnvironment(MarketConfig(**ec.params))
            elif ec.type == "economic":
                environments["economic"] = EconomicEnvironment(EconomicConfig(**ec.params))
        if not environments:
            environments["social"] = SocialEnvironment(SocialConfig())
        return environments

    def _create_agents(self, entities: list[Entity], env_names: list[str]) -> dict[str, Agent]:
        agents = {}
        for entity in entities:
            agent = Agent(
                id=entity.id,
                name=entity.name,
                persona=f"You are {entity.name}. {entity.summary}",
                environments=env_names,
                belief_state=BeliefState(),
                config=AgentActivityConfig(),
            )
            agents[agent.id] = agent
        return agents

    def _find_env_for_action(
        self, action_name: str, environments: dict[str, Any], agent: Agent
    ) -> str:
        for env_name in agent.environments:
            if env_name in environments:
                tool_names = {t.name for t in environments[env_name].get_tools()}
                if action_name in tool_names:
                    return env_name
        return agent.environments[0] if agent.environments else "unknown"


# ---------------------------------------------------------------------------
# Belief dynamics integration
# ---------------------------------------------------------------------------


def _apply_belief_updates(
    agents: dict[str, Agent],
    round_records: list[ActionRecord],
    topic: str,
) -> None:
    """Update each agent's belief state from the other agents' posts this round.

    Mutates Agent.belief_state in place. Own posts are skipped (agents don't
    influence themselves). Stance is scored from post text via
    simswarm.stance.score_stance.
    """
    # Build the exposure payload shape that belief.update_beliefs expects.
    # Only POST-like actions count as "exposures" — browse/follow/etc don't
    # carry a stance.
    post_actions = [
        r for r in round_records
        if r.success
        and r.action_type.lower() in ("create_post", "post", "comment", "reply")
    ]

    posts_by_author: dict[str, list[dict[str, Any]]] = {}
    for action in post_actions:
        text = (action.action_args or {}).get("text") or \
            (action.action_args or {}).get("content") or ""
        if not text:
            continue
        stance = score_stance(text)
        # content_hash need only be unique per post within the run so
        # exposure_history can dedupe repeated exposures.
        content_hash = f"r{action.round_num}:{action.agent_id}:{hash(text) & 0xffffffff:08x}"
        posts_by_author.setdefault(action.agent_id, []).append({
            "author": action.agent_name,
            "content_hash": content_hash,
            "stance": stance,
            "likes": 0,  # engagement counts aren't tracked yet; follow-up
        })

    if not posts_by_author:
        return

    for agent_id, agent in agents.items():
        exposures = [
            post for author, posts in posts_by_author.items()
            if author != agent_id
            for post in posts
        ]
        if not exposures:
            continue
        agent.belief_state = update_beliefs(
            state=agent.belief_state,
            posts=exposures,
            topic=topic,
            own_likes=0,
            own_dislikes=0,
        )
