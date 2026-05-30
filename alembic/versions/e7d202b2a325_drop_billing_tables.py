"""drop billing tables

Removes the credit_entries and credit_packs tables. Part of the open-source
pivot (billing removed). The simulation_jobs.credits_charged column is
intentionally NOT dropped — it is kept as a dead, default-0 legacy column.
Verify the tables exist (\\dt) before applying to a live DB — alembic_version
reports intent, not reality.

Revision ID: e7d202b2a325
Revises: x5y6z7a8b9c0
Create Date: 2026-05-28 19:18:30.535858

"""
from alembic import op
import sqlalchemy as sa

revision = 'e7d202b2a325'
down_revision = 'x5y6z7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "credit_packs" in tables:
        op.drop_table("credit_packs")
    if "credit_entries" in tables:
        op.drop_table("credit_entries")


def downgrade() -> None:
    op.create_table(
        "credit_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_entries_user_id", "credit_entries", ["user_id"])
    op.create_table(
        "credit_packs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
