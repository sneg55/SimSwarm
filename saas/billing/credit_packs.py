from dataclasses import dataclass

from saas.constants.tiers import TIER_CREDITS


@dataclass(frozen=True)
class CreditPack:
    name: str
    credits: int
    price_cents: int
    description: str


# NOTE: The credit_packs DB table is the primary source of truth for pack definitions.
# These hardcoded packs serve as a fallback only (e.g. before migrations run or in tests
# where the DB table has not been seeded). Prefer reading from the DB via the
# GET /api/billing/packs endpoint or the CreditPack SQLAlchemy model.
CREDIT_PACKS: dict[str, CreditPack] = {
    "starter": CreditPack(name="Starter", credits=100, price_cents=1900, description="3-4 small simulations"),
    "pro": CreditPack(name="Pro", credits=500, price_cents=7900, description="15-20 medium simulations"),
    "heavy": CreditPack(name="Heavy", credits=2000, price_cents=24900, description="Large-scale or frequent use"),
}


def get_pack(pack_id: str) -> CreditPack:
    return CREDIT_PACKS[pack_id]


def get_tier_cost(tier: str) -> int:
    return TIER_CREDITS[tier]
