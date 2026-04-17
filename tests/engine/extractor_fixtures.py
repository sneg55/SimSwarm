"""Shared fixtures for extractor tests."""
from __future__ import annotations

from simswarm.types import ActionRecord

SAMPLE_LOG: list[ActionRecord] = [
    # Round 1 — agent-alpha creates post, agent-beta creates post
    ActionRecord(
        round_num=1,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="create_post",
        platform="twitter",
        action_args={"content": "Support the new trade deal — great opportunity!"},
        timestamp="2026-04-08T10:00:00Z",
        success=True,
    ),
    ActionRecord(
        round_num=1,
        agent_id="agent-beta",
        agent_name="Bob",
        action_type="CREATE_POST",
        platform="reddit",
        action_args={"content": "I oppose this policy — danger ahead."},
        timestamp="2026-04-08T10:01:00Z",
        success=True,
    ),
    # Round 1 — agent-alpha likes something
    ActionRecord(
        round_num=1,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="like_post",
        platform="twitter",
        action_args={"target_id": "post-1"},
        timestamp="2026-04-08T10:02:00Z",
        success=True,
    ),
    # Round 1 — agent-gamma follows agent-alpha
    ActionRecord(
        round_num=1,
        agent_id="agent-gamma",
        agent_name="Carol",
        action_type="follow",
        platform="twitter",
        action_args={"target_id": "agent-alpha", "target_name": "Alice"},
        timestamp="2026-04-08T10:03:00Z",
        success=True,
    ),
    # Round 1 — agent-alpha follows agent-gamma (mutual)
    ActionRecord(
        round_num=1,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="follow",
        platform="twitter",
        action_args={"target_id": "agent-gamma", "target_name": "Carol"},
        timestamp="2026-04-08T10:04:00Z",
        success=True,
    ),
    # Round 2 — agent-beta creates another post
    ActionRecord(
        round_num=2,
        agent_id="agent-beta",
        agent_name="Bob",
        action_type="CREATE_POST",
        platform="twitter",
        action_args={"content": "Recovery looking good — progress on all fronts."},
        timestamp="2026-04-08T10:10:00Z",
        success=True,
    ),
    # Round 2 — agent-alpha comments
    ActionRecord(
        round_num=2,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="create_comment",
        platform="twitter",
        action_args={"content": "Agreed, very positive sign."},
        timestamp="2026-04-08T10:11:00Z",
        success=True,
    ),
    # Round 2 — agent-delta does nothing
    ActionRecord(
        round_num=2,
        agent_id="agent-delta",
        agent_name="Dave",
        action_type="do_nothing",
        platform="twitter",
        action_args={},
        timestamp="2026-04-08T10:12:00Z",
        success=True,
    ),
    # Round 2 — agent-beta buys on market
    ActionRecord(
        round_num=2,
        agent_id="agent-beta",
        agent_name="Bob",
        action_type="buy_shares",
        platform="polymarket",
        action_args={"market_id": "gdp_rise_q4", "outcome": "yes", "amount": 250},
        action_result={"side": "buy", "market_id": "gdp_rise_q4", "outcome": "yes",
                       "cost": 250.0, "shares": 403.2, "price": 0.62, "round": 2},
        timestamp="2026-04-08T10:13:00Z",
        success=True,
    ),
    # Round 3 — agent-alpha sells shares
    ActionRecord(
        round_num=3,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="sell_shares",
        platform="polymarket",
        action_args={"market_id": "inflation_below_3pct", "outcome": "no", "shares": 100},
        action_result={"side": "sell", "market_id": "inflation_below_3pct", "outcome": "no",
                       "proceeds": 45.0, "shares": 100.0, "price": 0.45, "round": 3},
        timestamp="2026-04-08T10:20:00Z",
        success=True,
    ),
    # Round 3 — agent-gamma follows agent-beta (one-way)
    ActionRecord(
        round_num=3,
        agent_id="agent-gamma",
        agent_name="Carol",
        action_type="follow",
        platform="reddit",
        action_args={"target_id": "agent-beta", "target_name": "Bob"},
        timestamp="2026-04-08T10:21:00Z",
        success=True,
    ),
    # Round 3 — failed post action (still counted)
    ActionRecord(
        round_num=3,
        agent_id="agent-delta",
        agent_name="Dave",
        action_type="create_post",
        platform="twitter",
        action_args={"content": "This is a test post that failed"},
        timestamp="2026-04-08T10:22:00Z",
        success=False,
    ),
]
