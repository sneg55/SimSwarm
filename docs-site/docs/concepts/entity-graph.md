---
sidebar_label: Entity Graph
---

# Entity graph

The entity graph is the interactive map of who's who in a simulation and how they
related to one another. It's one of the four result views, rendered as a node-and-edge
diagram you can pan, zoom, and click into.

## Nodes: the agents

Each node is one agent (one entity the simulation ran on). Beyond its name and type, a
node carries activity stats computed from the chat log: how many actions it took, how
many posts it authored, and how many rounds it was active. This lets the graph show at a
glance who drove the conversation and who stayed quiet, not just who was present.

## Edges: two kinds of relationship

Edges come from two sources, and both appear on the same graph:

1. Interaction edges are derived deterministically from the chat log. When one agent
   follows, replies to, votes on, reposts, or mentions another, that becomes a directed
   edge labeled by the interaction type (a negative vote becomes a *dislike* edge, a
   positive one a *like*). Repeated interactions between the same pair collapse into a
   single edge whose weight is the count, so a thick edge means a strong, repeated tie.
   Mentions are detected both from `@handle` references and from full entity names
   appearing in post text, and post-targeted actions are resolved back to the post's
   author so a reply links the two agents, not the agent and a post ID.

2. Semantic relationship edges are derived by an LLM that re-reads a sample of the
   transcript and proposes typed edges between entities, relationships like
   *supports*, *disagrees with*, or *responds to*, each optionally carrying a short fact
   describing the relationship. These typed edges are merged alongside the interaction
   edges. The extraction logs its raw output and retries once on a parse failure, and any
   relationship whose endpoints don't map to known entities is dropped rather than
   guessed.

## How it's presented

The graph ships as a snapshot of nodes, edges, and metadata (totals, the number of
rounds, and the set of entity types) that the frontend renders with Cytoscape.js.
Together the two edge types give you both the *mechanical* structure of the run (who
interacted with whom, how often) and its *semantic* structure (what those interactions
meant) on a single canvas.
