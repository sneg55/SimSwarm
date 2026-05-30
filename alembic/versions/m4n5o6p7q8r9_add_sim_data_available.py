"""add sim_data_available column to simulation_jobs

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("sim_data_available", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "sim_data_available")
