"""Scale max_rounds with tier: small=100, medium=150, large=200

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-04-07
"""
from alembic import op

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE model_routing SET max_rounds = 100 WHERE sim_tier = 'small';")
    op.execute("UPDATE model_routing SET max_rounds = 150 WHERE sim_tier = 'medium';")
    op.execute("UPDATE model_routing SET max_rounds = 200 WHERE sim_tier = 'large';")


def downgrade() -> None:
    op.execute("UPDATE model_routing SET max_rounds = 200 WHERE sim_tier IN ('small', 'medium', 'large');")
