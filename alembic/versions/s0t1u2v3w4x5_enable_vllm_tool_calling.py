"""enable vLLM tool-call parser for Qwen3

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-04-08
"""
from alembic import op

revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None

NEW_VLLM_ARGS = "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes"
OLD_VLLM_ARGS = "--max-model-len 32768"


def upgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET vllm_args = '{NEW_VLLM_ARGS}'
        WHERE vllm_args = '{OLD_VLLM_ARGS}';
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET vllm_args = '{OLD_VLLM_ARGS}'
        WHERE vllm_args = '{NEW_VLLM_ARGS}';
    """)
