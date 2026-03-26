from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


class ModelRouting(Base):
    __tablename__ = "model_routing"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sim_tier: Mapped[str] = mapped_column(String(20), unique=True)
    model_id: Mapped[str] = mapped_column(String(255))
    gpu_type: Mapped[str] = mapped_column(String(50))
    max_rounds: Mapped[int] = mapped_column(Integer, default=200)
    vllm_args: Mapped[str | None] = mapped_column(Text, nullable=True)
