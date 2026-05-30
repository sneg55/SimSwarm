# Golden Files

Saved simulation outputs used as regression baselines.

## How to populate

Run a simulation and copy results:

    # Small sim (5 agents, 15 rounds)
    cp /tmp/results/chat_log.json tests/contracts/golden/small_sim_chat_log.json
    cp /tmp/results/graph_data.json tests/contracts/golden/small_sim_graph_data.json
    cp /tmp/results/structured_results.json tests/contracts/golden/small_sim_structured.json

    # Sim with prediction market
    cp /tmp/results/chat_log.json tests/contracts/golden/market_sim_chat_log.json
    # ... etc

    # Sim with web enrichment
    cp /tmp/results/chat_log.json tests/contracts/golden/enriched_sim_chat_log.json
    # ... etc

Tests skip gracefully when golden files are missing.
