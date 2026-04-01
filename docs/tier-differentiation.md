# Tier Differentiation: Quality vs Cost Analysis

## Pipeline Cost Drivers

Each simulation has 5 GPU-bound stages, each making LLM calls on the rented GPU:

| Stage | LLM calls | Scales with |
|-------|-----------|-------------|
| 1. Ontology | 1 call | Fixed |
| 2. Knowledge graph (NER) | ~1 per chunk | Seed text length |
| 3. Profile generation | **1 per entity** | Entity count |
| 4. Simulation rounds | **agents_per_round x rounds** | Both |
| 5. Report (ReACT sections) | ~25-30 calls (search + interview + write) | Roughly fixed |

## Levers

### Entity count (e.g., small=25, medium=60, large=150)

**Quality impact:** More entities = more diverse perspectives in the simulation. With 25 agents you get key players only. With 60 you get secondary actors, media, public opinion proxies. With 150 you get niche voices that create surprising emergent behaviors.

**Cost impact:** Profile generation is the big one -- each entity needs a full LLM call with graph retrieval + web enrichment. Observed timing:
- 22 entities: ~4 min profile gen
- 27 entities: ~5 min profile gen

Roughly **linear scaling**. 60 entities ~12 min, 150 entities ~30 min.

Simulation rounds also get heavier -- more agents posting per round means more inference per round.

### Max rounds (e.g., small=200, medium=500, large=1000)

**Quality impact:** More rounds = longer simulated timeline = narrative arcs develop. At 200 rounds, you get initial reactions and early trends. At 500, you see counter-narratives forming and coalitions shifting. At 1000, you see second-order effects and prediction market convergence.

The report writer benefits most -- more data points for the ReACT sections to analyze, richer contradiction detection, more meaningful trajectory analysis.

**Cost impact:** 200 rounds with 22 agents took ~80s of actual simulation. Scaling is roughly `rounds x agents_active_per_round / parallelism`. 500 rounds with 60 agents would be ~8-10 min of simulation time. Not the biggest cost driver since inference is batched.

### Model size (e.g., 32B-AWQ vs 72B-AWQ vs 72B full)

**Quality impact:** Biggest quality lever. The model runs every agent persona, generates every post, evaluates every prediction market. A smarter model means:
- More coherent agent personas (less "breaking character")
- Better causal reasoning in agent posts
- Higher quality report sections (the ReACT writer uses the same model)

32B-AWQ is good. 72B would be noticeably better at maintaining distinct agent voices over long simulations.

**Cost impact:** Biggest cost lever too.
- 32B-AWQ on A100 40GB: works, ~$0.70-1.00/hr spot
- 32B-AWQ on L40S 48GB: works, ~$0.50-0.80/hr spot
- 72B-AWQ needs H100 80GB: ~$2.00-3.00/hr spot
- 72B full precision needs 2xH100: ~$5.00/hr spot

## Cost Estimates Per Tier

Based on observed demo timing (2026-03-31) + RunPod spot rates:

| | Small (current) | Small (tuned) | Medium (tuned) | Large (tuned) |
|---|---|---|---|---|
| **Entities** | ~22 (auto) | 25 cap | 60 cap | 150 cap |
| **Max rounds** | 200 | 200 | 500 | 1000 |
| **Model** | 32B-AWQ | 32B-AWQ | 32B-AWQ | 72B-AWQ |
| **GPU** | A100 40GB | A100 40GB | A100 40GB | H100 80GB |
| **Est. pipeline time** | ~22 min | ~22 min | ~45 min | ~2.5 hr |
| **Est. GPU cost** | ~$0.35 | ~$0.35 | ~$0.70 | ~$6.00 |
| **Credits charged** | 30 | 30 | 90 | 300 |
| **Credit pack price** | $0.57 | $0.57 | $1.71 | $5.70 |
| **Margin** | ~38% | ~38% | ~59% | ~5% |

## Recommendations

1. **Highest ROI change:** Cap entity count per tier. It creates the most visible difference in output (more agents = more voices in the report) while scaling cost predictably.

2. **Keep model size consistent for small/medium** -- both on 32B-AWQ. The cost jump to 72B is steep and only justified for large tier where users pay $5.70/sim and expect premium quality.

3. **Rounds matter less visually** -- the difference between 200 and 500 rounds is less noticeable to a non-technical user reading the report than 25 vs 60 distinct agent voices.

## Current State (as of 2026-03-31)

All three tiers use the same model (Qwen2.5-32B-AWQ) and same max_rounds (200). The only actual difference is GPU class (A100 vs H100). Entity count is determined by the ontology generator based on seed text, not capped by tier. The agent count ranges shown in the UI (1-500, 501-2000, 2001-10000) are aspirational labels, not enforced limits.
