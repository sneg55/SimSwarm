from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.credit_entry import CreditEntry


class InsufficientCreditsError(Exception):
    """Raised when a user does not have enough credits for an operation."""
    pass


class CreditLedger:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_balance(self, user_id: str) -> int:
        result = await self.session.execute(
            select(func.sum(CreditEntry.amount)).where(CreditEntry.user_id == user_id)
        )
        total = result.scalar()
        return total if total is not None else 0

    async def credit(
        self,
        user_id: str,
        amount: int,
        description: str,
        stripe_session_id: str | None = None,
    ) -> CreditEntry:
        entry = CreditEntry(
            user_id=user_id,
            amount=amount,
            description=description,
            stripe_session_id=stripe_session_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def debit(
        self,
        user_id: str,
        amount: int,
        description: str,
        job_id: int | None = None,
    ) -> CreditEntry:
        balance = await self.get_balance(user_id)
        if balance < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits: balance={balance}, required={amount}"
            )
        entry = CreditEntry(
            user_id=user_id,
            amount=-amount,
            description=description,
            job_id=job_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_history(self, user_id: str) -> list[CreditEntry]:
        result = await self.session.execute(
            select(CreditEntry)
            .where(CreditEntry.user_id == user_id)
            .order_by(CreditEntry.created_at.asc())
        )
        return list(result.scalars().all())
