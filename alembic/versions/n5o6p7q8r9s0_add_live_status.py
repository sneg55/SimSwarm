"""add live_status column to simulation_jobs

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("live_status", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "live_status")
