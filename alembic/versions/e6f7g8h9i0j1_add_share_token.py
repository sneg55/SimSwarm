"""add share_token to simulation_jobs

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6f7g8h9i0j1'
down_revision = 'd5e6f7g8h9i0'

def upgrade():
    op.add_column('simulation_jobs', sa.Column('share_token', sa.String(64), nullable=True))
    op.create_index('ix_simulation_jobs_share_token', 'simulation_jobs', ['share_token'], unique=True)

def downgrade():
    op.drop_index('ix_simulation_jobs_share_token')
    op.drop_column('simulation_jobs', 'share_token')
