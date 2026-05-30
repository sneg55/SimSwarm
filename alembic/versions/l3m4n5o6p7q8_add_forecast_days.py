"""add forecast_days column to simulation_jobs

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("forecast_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "forecast_days")
