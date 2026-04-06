"""update model_routing to Qwen3-14B

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-04-06
"""
from alembic import op

revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None

# Qwen3-14B: same quality as Qwen2.5-32B at half the compute cost.
# No AWQ quantization needed — 14B fits on 40GB VRAM natively.
# Lower VRAM requirement allows using cheaper GPUs (L40S for all tiers).
QWEN3_MODEL = "Qwen/Qwen3-14B"
QWEN3_VLLM_ARGS = "--max-model-len 32768"

# Previous model for downgrade
QWEN25_MODEL = "Qwen/Qwen2.5-32B-Instruct-AWQ"
QWEN25_VLLM_ARGS = "--quantization awq --max-model-len 32768"


def upgrade() -> None:
    # Update all tiers to Qwen3-14B with cheaper GPU options
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN3_MODEL}',
            vllm_args = '{QWEN3_VLLM_ARGS}',
            gpu_type = 'NVIDIA L40S'
        WHERE sim_tier IN ('small', 'medium', 'large');
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN25_MODEL}',
            vllm_args = '{QWEN25_VLLM_ARGS}',
            gpu_type = 'a100-40gb'
        WHERE sim_tier = 'small';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET model_id = '{QWEN25_MODEL}',
            vllm_args = '{QWEN25_VLLM_ARGS}',
            gpu_type = 'h100-80gb'
        WHERE sim_tier IN ('medium', 'large');
    """)
