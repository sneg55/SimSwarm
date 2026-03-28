from unittest.mock import patch, MagicMock


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.api.jobs.run_simulation_task.delay", return_value=mock_task)


async def test_no_credits_returns_402(client, auth_headers, seeded_routing):
    """User with zero credits cannot create a job."""
    response = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",
        },
    )
    assert response.status_code == 402


async def test_insufficient_credits_returns_402(client, auth_headers, db_session, seeded_routing):
    """User with some but not enough credits gets 402."""
    from saas.billing.ledger import CreditLedger
    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=10, description="A little credit")
    await db_session.commit()

    response = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",  # costs 30
        },
    )
    assert response.status_code == 402


async def test_job_creation_deducts_credits(client, auth_headers, db_session, seeded_routing):
    """Successful job creation deducts correct credits from balance."""
    from saas.billing.ledger import CreditLedger
    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=200, description="Test credits")
    await db_session.commit()

    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed",
                "goal": "Test goal",
                "tier": "small",  # costs 30
            },
        )
    assert response.status_code == 201

    balance = await ledger.get_balance(user_id)
    assert balance == 170  # 200 - 30


async def test_large_job_deducts_large_credits(client, auth_headers, db_session, seeded_routing):
    """Large tier job deducts 300 credits."""
    from saas.billing.ledger import CreditLedger
    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=500, description="Test credits")
    await db_session.commit()

    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed for large simulation",
                "goal": "Test goal",
                "tier": "large",  # costs 300
            },
        )
    assert response.status_code == 201

    balance = await ledger.get_balance(user_id)
    assert balance == 200  # 500 - 300
