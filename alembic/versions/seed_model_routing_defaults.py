"""seed model routing defaults

Revision ID: a1b2c3d4e5f6
Revises: 2b8217a29c38
Create Date: 2026-03-26 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2b8217a29c38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO model_routing (sim_tier, model_id, gpu_type, max_rounds, vllm_args)
        VALUES
            ('small', 'Qwen2.5-32B-Instruct-AWQ', 'a100-40gb', 200, '--quantization awq --max-model-len 32768'),
            ('medium', 'Qwen2.5-32B-Instruct-AWQ', 'h100-80gb', 200, '--quantization awq --max-model-len 32768'),
            ('large', 'Qwen2.5-32B-Instruct-AWQ', 'h100-80gb', 200, '--quantization awq --max-model-len 32768')
        ON CONFLICT (sim_tier) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM model_routing WHERE sim_tier IN ('small', 'medium', 'large');")
