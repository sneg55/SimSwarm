from dataclasses import dataclass

from saas.tiers import TIER_CREDITS


@dataclass(frozen=True)
class CreditPack:
    name: str
    credits: int
    price_cents: int
    description: str


CREDIT_PACKS: dict[str, CreditPack] = {
    "starter": CreditPack(name="Starter", credits=100, price_cents=1900, description="3-4 small simulations"),
    "pro": CreditPack(name="Pro", credits=500, price_cents=7900, description="15-20 medium simulations"),
    "heavy": CreditPack(name="Heavy", credits=2000, price_cents=24900, description="Large-scale or frequent use"),
}


def get_pack(pack_id: str) -> CreditPack:
    return CREDIT_PACKS[pack_id]


def get_tier_cost(tier: str) -> int:
    return TIER_CREDITS[tier]
