"""add result_graph column to simulation_jobs

Revision ID: b3f4g5h6i7j8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3f4g5h6i7j8'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('simulation_jobs', sa.Column('result_graph', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'result_graph')
