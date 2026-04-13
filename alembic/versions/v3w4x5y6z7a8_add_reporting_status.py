"""add REPORTING job status

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-04-13
"""
from alembic import op

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'REPORTING' AFTER 'RUNNING'")
    op.execute("BEGIN")


def downgrade() -> None:
    # Postgres does not support removing enum values safely; noop.
    pass
