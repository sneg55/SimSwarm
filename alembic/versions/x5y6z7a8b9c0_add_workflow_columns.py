"""add workflow_id columns

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-04-19

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('simulation_jobs', sa.Column('workflow_id', sa.String(length=255), nullable=True))
    op.add_column('simulation_jobs', sa.Column('workflow_run_id', sa.String(length=255), nullable=True))
    op.create_index('ix_simulation_jobs_workflow_id', 'simulation_jobs', ['workflow_id'])


def downgrade() -> None:
    op.drop_index('ix_simulation_jobs_workflow_id', table_name='simulation_jobs')
    op.drop_column('simulation_jobs', 'workflow_run_id')
    op.drop_column('simulation_jobs', 'workflow_id')
