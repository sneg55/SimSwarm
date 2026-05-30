"""Tool schemas exposed by the market environment to the LLM agent layer."""
from __future__ import annotations

from simswarm.types import Tool


def market_tools() -> list[Tool]:
    """Return the action tools agents may call against a market environment."""
    return [
        Tool(
            name="buy_shares",
            description="Buy YES or NO shares of a market with USD.",
            parameters={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "outcome": {"type": "string", "enum": ["yes", "no"]},
                    "amount": {"type": "number", "description": "USD to spend"},
                },
                "required": ["market_id", "outcome", "amount"],
            },
        ),
        Tool(
            name="sell_shares",
            description="Sell YES or NO shares you hold in a market.",
            parameters={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "outcome": {"type": "string", "enum": ["yes", "no"]},
                    "shares": {"type": "number"},
                },
                "required": ["market_id", "outcome", "shares"],
            },
        ),
        Tool(
            name="browse_markets",
            description="List all open markets and their current prices.",
            parameters={"type": "object", "properties": {}},
        ),
        Tool(
            name="comment_on_market",
            description="Post a comment about a market.",
            parameters={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["market_id", "text"],
            },
        ),
        Tool(
            name="do_nothing",
            description="Take no market action this round.",
            parameters={"type": "object", "properties": {}},
        ),
    ]
