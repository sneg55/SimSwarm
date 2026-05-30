---
sidebar_label: Neo4j
---

# Neo4j

Neo4j is the graph database used during a simulation run. It is configured by environment variables and is not part of the main `docker-compose.yml` — it runs as a separate service.

## Configuration

| Variable | Default |
|----------|---------|
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | Required — no default |

`NEO4J_PASSWORD` is a required `Settings` field (`saas/config.py`) with no default, so a misconfigured instance fails fast. These three values are forwarded into the GPU pod's environment (`saas/jobs/config.py`), where the worker waits for Neo4j to be reachable (`infra/docker/service_init.py: wait_for_neo4j`) before running.

## Running it

A standalone Compose file ships at `infra/neo4j/docker-compose.yml`:

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    ports:
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    restart: unless-stopped
```

Point `NEO4J_URI` at this host. In production it commonly runs on a separate VPS, e.g. `bolt://<neo4j-host>:7687`.

## What degrades without it

The in-app entity-graph **view** is built pure-Python from the simulation's action log by `simswarm.graph.build_graph` and stored as the job's `result_graph` JSON, then rendered with Cytoscape (`GET /api/jobs/{job_id}/graph`). That rendering path does not query Neo4j at view time.

Neo4j is consumed during the run on the pod. If it is unreachable, the worker's `wait_for_neo4j` gate blocks pod startup, so the simulation cannot proceed. Treat a reachable Neo4j (matching `NEO4J_URI` / `NEO4J_PASSWORD`) as a prerequisite for running simulations.
