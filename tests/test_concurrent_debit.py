import pytest
from saas.billing.ledger import CreditLedger, InsufficientCreditsError


async def test_debit_rejects_when_insufficient(db_session):
    """Basic debit rejection still works with new implementation."""
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id="test-user", amount=50, description="initial")
    await db_session.flush()

    with pytest.raises(InsufficientCreditsError):
        await ledger.debit(user_id="test-user", amount=80, description="too much")


async def test_debit_succeeds_when_sufficient(db_session):
    """Basic debit success still works."""
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id="test-user", amount=100, description="initial")
    await db_session.flush()

    entry = await ledger.debit(user_id="test-user", amount=30, description="charge")
    assert entry.amount == -30

    balance = await ledger.get_balance("test-user")
    assert balance == 70
