"""add error_events table

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-03-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'i0j1k2l3m4n5'
down_revision: Union[str, Sequence[str]] = 'h9i0j1k2l3m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'error_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False, server_default='ERROR'),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('traceback', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('request_path', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_error_events_timestamp', 'error_events', ['timestamp'])
    op.create_index('ix_error_events_source', 'error_events', ['source'])


def downgrade() -> None:
    op.drop_index('ix_error_events_source', table_name='error_events')
    op.drop_index('ix_error_events_timestamp', table_name='error_events')
    op.drop_table('error_events')
