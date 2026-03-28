"""add result_structured to simulation_jobs

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-03-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, Sequence[str]] = 'f7g8h9i0j1k2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'simulation_jobs',
        sa.Column('result_structured', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'result_structured')
