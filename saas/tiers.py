"""Centralized tier configuration — single source of truth."""

TIER_CREDITS = {"small": 30, "medium": 90, "large": 300}
TIER_TIMEOUTS = {"small": 2700, "medium": 18000, "large": 43200}
TIER_MAX_COST_USD = {"small": 1.50, "medium": 4.00, "large": 8.00}
VALID_TIERS = frozenset(TIER_CREDITS.keys())
