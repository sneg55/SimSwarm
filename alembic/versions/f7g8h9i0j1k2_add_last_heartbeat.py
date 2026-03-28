"""add last_heartbeat to simulation_jobs

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-03-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, Sequence[str]] = 'e6f7g8h9i0j1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'simulation_jobs',
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'last_heartbeat')
