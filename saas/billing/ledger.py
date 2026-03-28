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
        payment_intent_id: str | None = None,
    ) -> CreditEntry:
        entry = CreditEntry(
            user_id=user_id,
            amount=amount,
            description=description,
            stripe_session_id=stripe_session_id,
            payment_intent_id=payment_intent_id,
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
        from sqlalchemy import text
        from datetime import datetime, timezone

        try:
            result = await self.session.execute(
                text(
                    "INSERT INTO credit_entries (user_id, amount, description, job_id, created_at) "
                    "SELECT :user_id, :amount, :description, :job_id, :created_at "
                    "WHERE (SELECT COALESCE(SUM(amount), 0) FROM credit_entries WHERE user_id = CAST(:check_uid AS VARCHAR)) >= :required "
                    "RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "check_uid": user_id,
                    "amount": -amount,
                    "description": description,
                    "job_id": job_id,
                    "created_at": datetime.now(timezone.utc),
                    "required": amount,
                },
            )
            row = result.first()
            if row is None:
                balance = await self.get_balance(user_id)
                raise InsufficientCreditsError(
                    f"Insufficient credits: balance={balance}, required={amount}"
                )
            await self.session.flush()
            entry = await self.session.get(CreditEntry, row[0])
            return entry
        except InsufficientCreditsError:
            raise
        except Exception:
            # Fallback for SQLite or other engines that don't support
            # INSERT...SELECT...RETURNING reliably
            await self.session.rollback()
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

    async def session_credited(self, stripe_session_id: str | None) -> bool:
        """Return True if credits have already been added for a given Stripe session."""
        if stripe_session_id is None:
            return False
        result = await self.session.execute(
            select(func.count(CreditEntry.id)).where(
                CreditEntry.stripe_session_id == stripe_session_id,
                CreditEntry.amount > 0,
            )
        )
        return result.scalar() > 0

    async def get_credit_by_payment_intent(self, payment_intent_id: str) -> CreditEntry | None:
        result = await self.session.execute(
            select(CreditEntry).where(
                CreditEntry.payment_intent_id == payment_intent_id,
                CreditEntry.amount > 0,
            )
        )
        return result.scalar_one_or_none()

    async def get_history(self, user_id: str) -> list[CreditEntry]:
        result = await self.session.execute(
            select(CreditEntry)
            .where(CreditEntry.user_id == user_id)
            .order_by(CreditEntry.created_at.asc())
        )
        return list(result.scalars().all())
