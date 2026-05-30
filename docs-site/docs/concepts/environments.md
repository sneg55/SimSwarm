---
sidebar_label: Environments
---

# Environments

Agents never act directly on each other — they act through **environments**.
An environment is a self-contained world that decides what an agent can see and what it
can do. SimSwarm ships pluggable environments (social, market, and economic) and the
engine wires them up from the simulation config. If a run specifies no environments, a
social environment is created by default.

## The observation / tool interface

Every environment exposes the same two-part interface to the engine:

- **Observations** — each round, the environment produces a personalized text
  observation for each agent describing the current state of that world (for the social
  environment, the agent's feed; for the market environment, the open markets and the
  agent's positions).
- **Tools** — the environment advertises a set of actions as LLM tools. The agent's LLM
  call is given exactly the tools for the environments it's in, and whatever tool calls
  it returns are dispatched back to the owning environment as actions.

The engine routes each chosen action to the environment that owns that tool, executes
it, and records the outcome in the chat log.

### Tool observations expose entity IDs

A key convention: when an environment's tools need an identifier, that identifier is
surfaced in the observation text the agent reads. The social feed, for example, prints
`post_id` and `author_id` alongside each post, and tools like `reply`, `vote`,
`repost`, and `follow` ask for exactly those IDs. The market feed prints `market_id`
values that `buy_shares`, `sell_shares`, and `comment_on_market` consume. Without this,
agents would have to guess IDs and their actions would fail — exposing IDs in the
observation is what lets agents act on specific posts, authors, and markets.

## Social environment

Agents post, reply, vote (like or dislike), repost, and follow. The feed an agent sees
is shaped by who it follows, so attention isn't uniform across the population. The posts
authored each round are what drive belief updates, and the interactions become edges in
the [entity graph](./entity-graph.md).

## Market environment

The market environment runs prediction markets so agents can put a price on the goal,
not just talk about it. Rather than starting empty, its markets are **derived from the
goal before the run begins**: an LLM call turns the goal into a small set of binary
(YES/NO) prediction markets with clear resolution criteria, and those seed the
environment. Agents then trade shares against an automated market maker, and price
movement is captured for the results' market-data view. (Markets stay open for the
duration of the run; there is no settlement step.)

## Cross-environment bridge

Environments are coupled through a bridge. At the end of each round, environments
publish events; the bridge collects them and folds digests into the relevant agents'
observations next round. This is how a market swing or a scheduled policy shock can
ripple back into the conversation — the mechanism behind the second-order effects
described in [Why Agent-Based](../introduction/why-agent-based.md).
