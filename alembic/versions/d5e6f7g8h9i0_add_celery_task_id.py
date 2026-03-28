"""add celery_task_id to simulation_jobs

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-03-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7g8h9i0'
down_revision: Union[str, Sequence[str]] = 'c4d5e6f7g8h9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('simulation_jobs', sa.Column('celery_task_id', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'celery_task_id')
