"""add pod_id, retry_count, duration columns to simulation_jobs and payment_intent_id to credit_entries

Revision ID: c4d5e6f7g8h9
Revises: b3f4g5h6i7j8
Create Date: 2026-03-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c4d5e6f7g8h9'
down_revision: Union[str, Sequence[str]] = 'b3f4g5h6i7j8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # simulation_jobs: pod tracking and duration metrics
    op.add_column('simulation_jobs', sa.Column('pod_id', sa.String(255), nullable=True))
    op.add_column('simulation_jobs', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('simulation_jobs', sa.Column('provision_seconds', sa.Integer(), nullable=True))
    op.add_column('simulation_jobs', sa.Column('pipeline_seconds', sa.Integer(), nullable=True))
    op.create_index('ix_simulation_jobs_pod_id', 'simulation_jobs', ['pod_id'])

    # credit_entries: link credits to Stripe payment intents for refund handling
    op.add_column('credit_entries', sa.Column('payment_intent_id', sa.String(255), nullable=True))
    op.create_index('ix_credit_entries_payment_intent_id', 'credit_entries', ['payment_intent_id'])


def downgrade() -> None:
    op.drop_index('ix_credit_entries_payment_intent_id', table_name='credit_entries')
    op.drop_column('credit_entries', 'payment_intent_id')

    op.drop_index('ix_simulation_jobs_pod_id', table_name='simulation_jobs')
    op.drop_column('simulation_jobs', 'pipeline_seconds')
    op.drop_column('simulation_jobs', 'provision_seconds')
    op.drop_column('simulation_jobs', 'retry_count')
    op.drop_column('simulation_jobs', 'pod_id')
