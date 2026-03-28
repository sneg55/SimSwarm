"""add key_insight column to simulation_jobs

Revision ID: d5e6f7g8h9
Revises: b3f4g5h6i7j8
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9"
down_revision = "b3f4g5h6i7j8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_jobs",
        sa.Column("key_insight", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_jobs", "key_insight")
