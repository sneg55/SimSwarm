"""add enrichment columns to simulation_jobs

Revision ID: j1k2l3m4n5o6
Revises: 656dca26764a
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, Sequence[str], None] = '656dca26764a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'simulation_jobs',
        sa.Column('enrich_web', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'simulation_jobs',
        sa.Column('enriched_seed', sa.Text(), nullable=True),
    )
    op.add_column(
        'simulation_jobs',
        sa.Column('enrichment_citations', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'enrichment_citations')
    op.drop_column('simulation_jobs', 'enriched_seed')
    op.drop_column('simulation_jobs', 'enrich_web')
