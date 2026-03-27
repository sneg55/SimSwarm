import enum
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    seed_text: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(20))
    credits_charged: Mapped[int] = mapped_column(Integer)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    pipeline_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_chat_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gpu_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
