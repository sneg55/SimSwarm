"""Add target_agents to model_routing

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_routing", sa.Column("target_agents", sa.Integer(), server_default="5"))
    op.execute("UPDATE model_routing SET target_agents = 15 WHERE sim_tier = 'small';")
    op.execute("UPDATE model_routing SET target_agents = 25 WHERE sim_tier = 'medium';")
    op.execute("UPDATE model_routing SET target_agents = 40 WHERE sim_tier = 'large';")


def downgrade() -> None:
    op.drop_column("model_routing", "target_agents")
