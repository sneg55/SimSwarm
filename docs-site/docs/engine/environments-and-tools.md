---
sidebar_label: Environments & Tools
---

# Environments and tools

Environments are the worlds agents act in. Each environment owns its state and decides what an
agent can see (`get_observations`), what an agent can do (`get_tools`), how an action resolves
(`execute_action`), and what cross-environment events it emits (`publish_events`). Three ship
in `simswarm/environments/`: `social`, `market`, `economic`.

## The environment protocol

`simswarm/environments/base.py` defines the structural protocol every environment satisfies:

```python
class Environment(Protocol):
    name: str
    def get_observations(self, agent: Agent) -> Observation: ...
    def execute_action(self, agent: Agent, action: Action) -> ActionResult: ...
    def get_tools(self) -> list[Tool]: ...
    def publish_events(self) -> list[Event]: ...
    def tick(self) -> None: ...
```

The engine instantiates environments in `Engine._create_environments` keyed by type string
(`"social"`, `"market"`, `"economic"`), passing `EnvironmentConfig.params` straight into the
matching config dataclass.

## The tool/action contract

`get_tools()` returns `simswarm.types.Tool` objects. Each `Tool` carries a `name`,
`description`, and a JSON-Schema `parameters` block, and serializes via `to_openai_schema()`
into the `{"type": "function", "function": {...}}` shape the LLM consumes. When the LLM emits
a tool call, the engine routes it by tool name to the owning environment (see
[Architecture](architecture.md)) and calls `execute_action`, which dispatches on
`action.action_type` through an internal handler dict. Unknown actions return
`ActionResult(success=False, data={"error": "Unknown action: ..."})`.

### IDs in observations

A recurring engine convention: if an action argument needs an ID, the corresponding
observation text must expose that ID. Agents only know IDs they've read in their feed.

- The social env's `get_observations` renders each post as
  `post_id=<uuid> author_id=<uuid> [<name>] <text> (score: <likes-dislikes>)`, so the LLM can
  pass `post_id` into `reply`/`vote`/`repost` and `agent_id` (the `author_id`) into `follow`.
- The market env renders `Market [<market_id>]: <question> | YES: x% | NO: y%`, where
  `market_id` is a deterministic slug derived from the question
  (`_question_to_slug`: lowercase, non-alphanumerics → underscores, capped at 40 chars,
  numeric suffix on collision). Agents reference it in `buy_shares`/`sell_shares`/
  `comment_on_market`.

## Social environment

`SocialEnvironment` (`environments/social.py`) is the default. `SocialConfig` controls
`threading`, `voting_mode` (default `"likes_only"`), feed weights
(`recency_weight=0.3`, `popularity_weight=0.4`, `relevance_weight=0.3`),
`echo_chamber_strength=0.5`, and `viral_threshold=5`.

**Tools:** `create_post` (`text`), `reply` (`post_id`, `text`), `vote` (`post_id`, `value`
enum `[1, -1]`), `repost` (`post_id`), `follow` (`agent_id`), `do_nothing`.

**State & handlers:** posts are stored in a `dict[str, Post]` keyed by a generated UUID; each
`Post` tracks `likes`, `dislikes`, `reposts`, `created_round`, `parent_id` (for threads), and
a `voters` set (one vote per agent; repeat votes fail). `_handle_vote` increments `likes`
when `value > 0`, otherwise `dislikes`. Posts and replies return `{"post_id": <uuid>}` in
their `ActionResult.data`, which is what `apply_belief_updates` and the extractors key on.

**Feed ranking:** `_rank_feed` scores top-level posts (`parent_id is None`) with
`recency_weight * recency + popularity_weight * log1p(likes + reposts) + relevance_weight *
relevance`, where `relevance` is `1.0` for followed authors and
`1.0 - echo_chamber_strength` otherwise. The top 20 are shown, each with up to 3 replies when
threading is on.

**Engagement & events:** `current_engagement()` returns `{post_id: (likes, dislikes)}` (the
engine feeds this into belief updates). `tick()` emits a `viral_post` event the first time a
post's `likes + reposts >= viral_threshold`.

## Market environment

`MarketEnvironment` (`environments/market.py`) is a constant-product AMM prediction market.
`MarketConfig` carries `markets` (list of `{"question", "initial_price_yes"}`),
`initial_balance=1000.0`, `initial_liquidity=500.0`, and `price_move_event_threshold=0.1`.
Each market initializes reserves from the seed price: `reserve_yes = liq*2*(1-price_yes)`,
`reserve_no = liq*2*price_yes`.

> The `initial_liquidity=500.0` default is deliberate. At liquidity 100, a single one-sided
> round could peg YES to ~0%/~100% (observed in sim 127); 500 keeps consensus prices roughly
> within `[10%, 90%]` while still permitting meaningful moves.

**Tools:** `buy_shares` (`market_id`, `outcome` enum `["yes","no"]`, `amount` in USD),
`sell_shares` (`market_id`, `outcome`, `shares`), `browse_markets`, `comment_on_market`
(`market_id`, `text`), `do_nothing`.

**AMM math:** this lives in `environments/market_amm.py`. `price_yes = reserve_no / (reserve_yes +
reserve_no)`. Buying YES injects USD into `reserve_no` and removes YES shares, preserving
`k = reserve_yes * reserve_no`. Each agent gets a `Portfolio` (lazily registered) with a
balance and per-market YES/NO share holdings. Buys debit balance and return
`{side, market_id, outcome, shares, cost, price, round}`; sells credit balance and return
`proceeds` instead of `cost`. `tick()` emits a `price_move` event when
`abs(price_yes - last_price) >= price_move_event_threshold`.

## Economic environment

`EconomicEnvironment` (`environments/economic.py`) is a rule-based macro model. `EconomicConfig`
has `labor_force=1000` and `metric_change_threshold=0.05`. Each agent becomes an
`EconomicActor` (role, balance, workforce, price, output).

**Tools:** `set_price` (`price`), `hire` (`count`), `fire` (`count`), `invest` (`amount`),
`allocate` (`target`, `amount`), `apply_policy` (`policy_name`, `description`, optional
`variable`/`value`), `do_nothing`.

`tick()` snapshots the previous metrics, recomputes aggregates
(`employment_rate = min(total_workforce / labor_force, 1.0)`, `avg_price` = mean of positive
prices, `total_output` = sum of outputs, `total_investment` = cumulative), then emits a
`metric_change` event for any metric whose absolute delta crosses `metric_change_threshold`.
`apply_policy` appends to `active_policies` and can set a scenario variable that surfaces in
later observations.

## Observation assembly

The engine wraps each environment's `Observation` into the agent's context. Observation text
is what the agent reasons over, so each environment renders a compact, ID-bearing,
human-readable block. The engine additionally appends a bridge digest and a `scenario`
observation (from `SimulationConfig.variables`) before the LLM call. See
[Architecture](architecture.md) for the full per-round flow and `build_context` in
`simswarm/llm.py` for how observations become chat messages.
