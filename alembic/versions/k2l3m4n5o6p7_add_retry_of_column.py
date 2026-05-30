"""add retry_of column to simulation_jobs

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("retry_of", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "retry_of")
