"""add credit_packs table

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-03-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'h9i0j1k2l3m4'
down_revision: Union[str, Sequence[str]] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    credit_packs_table = op.create_table(
        'credit_packs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )

    op.bulk_insert(
        credit_packs_table,
        [
            {
                'slug': 'starter',
                'name': 'Starter',
                'credits': 100,
                'price_cents': 1900,
                'stripe_price_id': None,
                'description': '3-4 small simulations',
                'active': True,
                'sort_order': 1,
            },
            {
                'slug': 'pro',
                'name': 'Pro',
                'credits': 500,
                'price_cents': 7900,
                'stripe_price_id': None,
                'description': '15-20 medium simulations',
                'active': True,
                'sort_order': 2,
            },
            {
                'slug': 'heavy',
                'name': 'Heavy',
                'credits': 2000,
                'price_cents': 24900,
                'stripe_price_id': None,
                'description': 'Large-scale or frequent use',
                'active': True,
                'sort_order': 3,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table('credit_packs')
