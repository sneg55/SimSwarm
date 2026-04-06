"""add resume_task_id column to simulation_jobs

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("resume_task_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "resume_task_id")
