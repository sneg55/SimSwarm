---
sidebar_label: Open Source & Self-Hosting
---

# Open Source & Self-Hosting

SimSwarm is MIT-licensed and self-hostable. The whole stack ships in one repository —
the native simulation engine, the FastAPI backend, the Vue frontend, and the GPU job
runner. There is no commercial billing layer: authenticated users on a self-hosted
instance submit simulations freely.

## One codebase, two postures

A single configuration flag, `DEMO_MODE`, switches the platform between its two modes:

- **`DEMO_MODE=false` (default) — full self-hosted platform.** Registration and job
  submission are enabled. This is what you run on your own infrastructure.
- **`DEMO_MODE=true` — read-only public demo.** Signups and job submission are disabled;
  only the browsable demo gallery and share/read endpoints stay open.

The public site at [simswarm.xyz](https://simswarm.xyz) runs with `DEMO_MODE=true`: it
is a read-only window onto a curated set of real simulations, not an account you can
sign up for. To actually run simulations, deploy your own instance.

## What you keep when self-hosting

The open-source platform retains everything that produces a simulation result:

- the swarm engine (`simswarm/`) — agents, environments, belief dynamics, extraction,
  graph build, and report generation;
- authentication, so a self-hosted instance can support multiple users;
- the full job lifecycle, from seed upload through GPU provisioning to the four result
  views.

## What it takes to run

Self-hosting brings up the stack with Docker Compose and requires credentials for the
external services the pipeline depends on — a GPU provider for the simulation workers,
an LLM provider for report generation, and object storage for simulation artifacts.
The exact set of environment variables and the bring-up steps are covered in the
self-hosting documentation; the project README's quickstart is the fastest path to a
running instance.

SimSwarm is released under the MIT license. The simulation engine is fully native, so
there is no copyleft engine dependency to inherit.
