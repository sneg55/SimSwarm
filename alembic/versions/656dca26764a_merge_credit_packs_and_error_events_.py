"""merge credit_packs and error_events branches

Revision ID: 656dca26764a
Revises: d5e6f7g8h9, i0j1k2l3m4n5
Create Date: 2026-03-29 17:25:44.800768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '656dca26764a'
down_revision: Union[str, Sequence[str], None] = ('d5e6f7g8h9', 'i0j1k2l3m4n5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
