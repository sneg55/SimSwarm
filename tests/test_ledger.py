import pytest
from saas.billing.ledger import CreditLedger, InsufficientCreditsError


async def test_initial_balance_zero(db_session):
    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance("user-new")
    assert balance == 0


async def test_credit_increases_balance(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-a", amount=100, description="Purchase")
    balance = await ledger.get_balance("user-a")
    assert balance == 100


async def test_debit_decreases_balance(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-b", amount=200, description="Purchase")
    await ledger.debit("user-b", amount=50, description="Job cost")
    balance = await ledger.get_balance("user-b")
    assert balance == 150


async def test_insufficient_credits_raises(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-c", amount=20, description="Purchase")
    with pytest.raises(InsufficientCreditsError):
        await ledger.debit("user-c", amount=50, description="Job cost")


async def test_multiple_transactions(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-d", amount=500, description="Pack 1")
    await ledger.credit("user-d", amount=100, description="Pack 2")
    await ledger.debit("user-d", amount=90, description="Job 1")
    await ledger.debit("user-d", amount=30, description="Job 2")
    balance = await ledger.get_balance("user-d")
    assert balance == 480


async def test_refund_credits(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-e", amount=100, description="Purchase")
    await ledger.debit("user-e", amount=100, description="Job")
    # Refund
    await ledger.credit("user-e", amount=100, description="Refund", stripe_session_id="sess_abc")
    balance = await ledger.get_balance("user-e")
    assert balance == 100


async def test_separate_users_isolated(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-x", amount=300, description="Purchase")
    await ledger.credit("user-y", amount=50, description="Purchase")
    assert await ledger.get_balance("user-x") == 300
    assert await ledger.get_balance("user-y") == 50


async def test_history_ordered(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-h", amount=500, description="Purchase")
    await ledger.debit("user-h", amount=30, description="Job 1", job_id=1)
    await ledger.debit("user-h", amount=90, description="Job 2", job_id=2)
    history = await ledger.get_history("user-h")
    assert len(history) == 3
    assert history[0].amount == 500
    assert history[1].amount == -30
    assert history[2].amount == -90
