from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


class CreditEntry(Base):
    __tablename__ = "credit_entries"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # positive=credit, negative=debit
    description: Mapped[str] = mapped_column(Text)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    credits: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
