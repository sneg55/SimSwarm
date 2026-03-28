# OASIS Paper Analysis — Applicability to FishCloud

**Paper:** OASIS: Open Agent Social Interaction Simulations with One Million Agents
**arXiv:** 2411.11581 (v5, March 2025)
**Authors:** Ziyi Yang, Zaibin Zhang, et al.

## Paper Summary

OASIS is a scalable multi-agent simulation platform that models social media dynamics (X, Reddit) using LLM-driven agents. It scales to 1M agents and demonstrates emergent phenomena: information propagation, group polarization, herd effects, and misinformation spread.

Core architecture: Environment Server, RecSys (recommendation system), LLM Agent Module (21 actions, chain-of-thought), Time Engine (24-dim hourly activity vectors), and Scalable Inferencer (distributed async GPU inference).

Key finding: larger agent populations produce qualitatively different and richer emergent behaviors — more diverse opinions, more pronounced group dynamics, and self-correction mechanisms that only appear at 10k+ agents.

## What We Can Apply to FishCloud

### 1. Scale-Dependent Pricing Justification

OASIS demonstrates that larger agent populations produce qualitatively different and richer emergent behaviors. Opinions become more diverse, group dynamics more pronounced, and self-correction mechanisms only appear at 10k+ agents. This directly validates our tiered credit model — higher tiers with more agents aren't just "more of the same," they unlock phenomena that smaller runs physically cannot produce. We should surface this in marketing copy and tier descriptions.

### 2. Recommendation System Layer

OASIS uses platform-specific RecSys (TwHIN-BERT for X, hot-score for Reddit) to filter what agents see. Their ablation shows removing RecSys severely hampers information spread accuracy. MiroFish could benefit from an optional recommendation/filtering layer in the adapter — letting users simulate how algorithmic curation shapes their prediction domain (e.g., how trending algorithms affect narrative spread).

### 3. Time Engine for Realistic Temporal Patterns

Their 24-dimensional hourly activity probability vectors ensure agents don't all act simultaneously. If MiroFish simulations currently use synchronous rounds, adding a temporal activity model could improve realism for time-sensitive predictions (market movements, news cycles). This could be a differentiating "realistic timing" option in our simulation config.

### 4. New Use Cases / Verticals

OASIS validated several simulation scenarios we could package as templates for our non-technical users:

- **Misinformation tracking** — their 1M-agent run showed misinformation sustains higher influence than official news across health, tech, entertainment, education
- **Group polarization analysis** — opinions shift toward extremes during social interaction; uncensored models show worse polarization
- **Herd effect detection** — agents show stronger herd behavior than humans, but self-correct at scale

These map to concrete FishCloud templates: "Brand Crisis Simulation," "Narrative Spread Forecast," "Market Sentiment Polarization."

### 5. Scalable Inference Architecture

Their distributed async inference with GPU resource management for concurrent agent requests is directly relevant to our RunPod orchestration. Key patterns:

- Asynchronous processing with batched LLM calls across GPU clusters
- Multi-processing architecture for concurrent inference
- Could inform how `saas/gpu/runpod_provider.py` manages multi-GPU jobs for large simulations

### 6. Synthetic User Profile Generation

OASIS generates up to 1M synthetic user profiles while preserving scale-free social network properties. We could offer a "seed population generator" feature — users upload a small seed document, and we generate a realistic agent population with diverse personas relevant to their domain, rather than requiring users to define every agent.

### 7. Platform-Specific Simulation Modules

Their modular design lets them swap between X and Reddit dynamics easily. We could offer platform presets — "Simulate as Twitter/X dynamics," "Simulate as Reddit dynamics," "Simulate as LinkedIn dynamics" — each with appropriate recommendation algorithms and interaction patterns. This makes FishCloud more tangible for marketers and strategists.

## What's Less Relevant

- Their ~30% NRMSE on propagation (decent but not great) — we should aim higher for a paid product
- The academic evaluation framework (GPT-4o-mini as judge) — our users want actionable reports, not academic metrics
- Their specific LLM backbone comparisons (Qwen, Llama, Internlm producing similar results) — we already handle model routing

## Bottom Line

The strongest takeaway is **scale matters** — and that's a natural upsell story for our credit tiers. The most implementable ideas are the **time engine**, **platform-specific presets**, and **seed population generator**, all of which would differentiate FishCloud from raw MiroFish access without requiring deep engine changes (they'd live in the adapter layer).
