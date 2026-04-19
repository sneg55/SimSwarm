import enum
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    seed_text: Mapped[str] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    credits_charged: Mapped[int] = mapped_column(Integer)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    pipeline_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_chat_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_graph: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gpu_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pod_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    provision_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_insight: Mapped[str | None] = mapped_column(String(200), nullable=True)
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    result_structured: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enrich_web: Mapped[bool] = mapped_column(default=True)
    enriched_seed: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_citations: Mapped[str | None] = mapped_column(Text, nullable=True)
    forecast_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sim_data_available: Mapped[bool] = mapped_column(default=False)
    live_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    markets_config: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)


class ModelRouting(Base):
    __tablename__ = "model_routing"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sim_tier: Mapped[str] = mapped_column(String(20), unique=True)
    model_id: Mapped[str] = mapped_column(String(255))
    gpu_type: Mapped[str] = mapped_column(String(50))
    max_rounds: Mapped[int] = mapped_column(Integer, default=200)
    vllm_args: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_agents: Mapped[int] = mapped_column(Integer, default=5)


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
