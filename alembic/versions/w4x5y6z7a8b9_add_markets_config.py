"""add markets_config column to simulation_jobs

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-04-17

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_jobs",
        sa.Column("markets_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_jobs", "markets_config")
