"""add DRAFT status, nullable goal and tier

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction.
    # Commit the current transaction first, then run outside it.
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'DRAFT' BEFORE 'PENDING'")
    op.execute("BEGIN")
    op.alter_column("simulation_jobs", "goal", existing_type=sa.Text(), nullable=True)
    op.alter_column("simulation_jobs", "tier", existing_type=sa.String(20), nullable=True)


def downgrade() -> None:
    # Set any NULL values to empty string before making columns NOT NULL again.
    op.execute("UPDATE simulation_jobs SET goal = '' WHERE goal IS NULL")
    op.execute("UPDATE simulation_jobs SET tier = '' WHERE tier IS NULL")
    op.alter_column("simulation_jobs", "goal", existing_type=sa.Text(), nullable=False)
    op.alter_column("simulation_jobs", "tier", existing_type=sa.String(20), nullable=False)
