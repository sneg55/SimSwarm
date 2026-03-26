import pytest


async def test_no_credits_returns_402(client):
    """User with zero credits cannot create a job."""
    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "broke-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",
        },
    )
    assert response.status_code == 402


async def test_insufficient_credits_returns_402(client, db_session):
    """User with some but not enough credits gets 402."""
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit("low-credits-user", amount=10, description="A little credit")
    await db_session.commit()

    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "low-credits-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",  # costs 30
        },
    )
    assert response.status_code == 402


async def test_job_creation_deducts_credits(client, db_session):
    """Successful job creation deducts correct credits from balance."""
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit("funded-user-1", amount=200, description="Test credits")
    await db_session.commit()

    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "funded-user-1",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",  # costs 30
        },
    )
    assert response.status_code == 201

    balance = await ledger.get_balance("funded-user-1")
    assert balance == 170  # 200 - 30


async def test_large_job_deducts_large_credits(client, db_session):
    """Large tier job deducts 300 credits."""
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit("funded-user-2", amount=500, description="Test credits")
    await db_session.commit()

    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "funded-user-2",
            "seed_text": "Test seed for large simulation",
            "goal": "Test goal",
            "tier": "large",  # costs 300
        },
    )
    assert response.status_code == 201

    balance = await ledger.get_balance("funded-user-2")
    assert balance == 200  # 500 - 300
