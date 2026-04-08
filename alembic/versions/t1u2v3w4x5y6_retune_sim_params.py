"""retune simulation params for working tool calling

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-04-08
"""
from alembic import op

revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None

# With tool calling active, rounds take ~80s each (8K context, L40S).
# Budget: timeout / 80s, with 20% headroom for report generation.
TOOL_CALL_VLLM = "--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes"
OLD_VLLM = "--max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes"


def upgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 25, target_agents = 10,
            vllm_args = '{TOOL_CALL_VLLM}'
        WHERE sim_tier = 'small';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 100, target_agents = 20,
            vllm_args = '{TOOL_CALL_VLLM}'
        WHERE sim_tier = 'medium';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 200, target_agents = 35,
            vllm_args = '{TOOL_CALL_VLLM}'
        WHERE sim_tier = 'large';
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 100, target_agents = 15,
            vllm_args = '{OLD_VLLM}'
        WHERE sim_tier = 'small';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 150, target_agents = 25,
            vllm_args = '{OLD_VLLM}'
        WHERE sim_tier = 'medium';
    """)
    op.execute(f"""
        UPDATE model_routing
        SET max_rounds = 200, target_agents = 40,
            vllm_args = '{OLD_VLLM}'
        WHERE sim_tier = 'large';
    """)
