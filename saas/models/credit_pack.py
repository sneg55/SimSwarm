from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


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
