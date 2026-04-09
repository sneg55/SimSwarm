"""Pluggable simulation environments."""
from simswarm.environments.social import SocialConfig, SocialEnvironment
from simswarm.environments.market import MarketConfig, MarketEnvironment
from simswarm.environments.economic import EconomicConfig, EconomicEnvironment

__all__ = [
    "SocialConfig", "SocialEnvironment",
    "MarketConfig", "MarketEnvironment",
    "EconomicConfig", "EconomicEnvironment",
]
