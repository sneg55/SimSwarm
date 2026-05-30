---
sidebar_label: What is SimSwarm
---

# What is SimSwarm

SimSwarm is a swarm-intelligence, agent-based simulation platform for prediction and
stress-testing. You upload a seed document describing a situation, set a prediction
goal, and run a simulation in which many LLM-driven agents debate, post, follow, and
trade across a simulated ecosystem. Instead of asking a single model "what happens
next?", SimSwarm lets a population of agents interact over a series of rounds and
surfaces the dynamics that emerge from those interactions.

## The user flow

1. **Seed document** — provide the source text the scenario is built from. Optionally,
   the seed can be enriched with live web and X/Twitter research before the run.
2. **Prediction goal** — state, in plain language, the question you want answered (for
   example, forecasting market response or community sentiment over a horizon).
3. **Run** — agents are derived from the seed and step through the simulation rounds.
4. **Results** — when the run completes you get four views of the output:
   - a deep-analysis **report** with grounded findings,
   - an interactive **entity graph** of participants and their relationships,
   - **prediction-market data** (price charts, trades), and
   - a full **chat replay** of every agent action, round by round.

## Who it's for

SimSwarm is aimed at domain experts and researchers who want to explore how a scenario
might unfold without writing simulation code. The wizard-driven flow takes a document
and a goal; the platform handles agent generation, the simulation loop, extraction, and
report assembly.

## Try it

A read-only public demo runs at [simswarm.xyz](https://simswarm.xyz), where you can
browse a gallery of real simulations and their outputs. SimSwarm is open source and
self-hostable — see [Open Source & Self-Hosting](./oss-and-self-host.md) to run your
own instance.
