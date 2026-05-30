---
sidebar_label: Explore the Demo
---

# Explore the demo

A read-only public demo runs at [simswarm.xyz](https://simswarm.xyz). Signups and job submission are disabled there (`DEMO_MODE=true`), but every curated result is browsable through its share link.

## Curated demos

These are the six curated demos shipped in `frontend/public/demos/index.json`:

| Prediction goal | Tier |
|-----------------|------|
| Predict global energy market response, supply chain disruptions, and government interventions over 30 days as the Hormuz crisis unfolds | large |
| Forecast crypto community sentiment and price narrative evolution in the 60 days following the Bitcoin halving | large |
| Predict creator migration patterns, competitor market share capture, and corporate AI content deal sentiment over 60 days | medium |
| Predict the regulatory cascade, class action momentum, and platform design changes over 90 days following the landmark verdict | medium |
| Predict opening weekend box office, cultural impact trajectory, and MCU franchise revival narrative over 90 days | small |
| Predict FAA regulatory response, airline industry operational changes, and public confidence impact over 60 days | small |

Each demo opens at its share URL (`/s/{token}`) and renders through the same `SharedResult` view used for any shared job.

## What each result panel shows

The shared-result view (`SharedResult.vue`) offers the same view modes as a logged-in result:

- **Story**: a meta row (participant count, forecast horizon in days, tier depth), a question-and-answer hero with the verdict and stakeholder positions, the findings the simulation surfaced as cards with citations, and a simulation-scale footer.
- **Graph**: the interactive entity graph (nodes, edges, metadata) rendered with the same Cytoscape visualization as the dashboard.
- **Report**: the full deep-analysis report with its table of contents, headed by the simulation title and tier.

Because the demo is read-only, the wizard and account actions are not available; you can only browse these published results.
