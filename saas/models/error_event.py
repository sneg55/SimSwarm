from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from saas.models.base import Base


class ErrorEvent(Base):
    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    level: Mapped[str] = mapped_column(String(20), default="ERROR")
    source: Mapped[str] = mapped_column(String(20))  # api, worker, gpu
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
