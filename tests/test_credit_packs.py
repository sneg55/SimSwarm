import pytest
from saas.billing.credit_packs import CREDIT_PACKS, TIER_CREDITS, get_pack, get_tier_cost


def test_three_packs_defined():
    assert len(CREDIT_PACKS) == 3
    assert "starter" in CREDIT_PACKS
    assert "pro" in CREDIT_PACKS
    assert "heavy" in CREDIT_PACKS


def test_starter_pack():
    pack = CREDIT_PACKS["starter"]
    assert pack.credits == 100
    assert pack.price_cents == 1900


def test_pro_pack():
    pack = CREDIT_PACKS["pro"]
    assert pack.credits == 500
    assert pack.price_cents == 7900


def test_heavy_pack():
    pack = CREDIT_PACKS["heavy"]
    assert pack.credits == 2000
    assert pack.price_cents == 24900


def test_tier_costs():
    assert TIER_CREDITS["small"] == 30
    assert TIER_CREDITS["medium"] == 90
    assert TIER_CREDITS["large"] == 300


def test_invalid_pack_raises_key_error():
    with pytest.raises(KeyError):
        get_pack("nonexistent")


def test_invalid_tier_raises_key_error():
    with pytest.raises(KeyError):
        get_tier_cost("nonexistent")
