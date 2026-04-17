"""Contract tests for ActionRecord."""
from __future__ import annotations

from simswarm.types import ActionRecord


class TestActionRecordActionResult:
    def test_action_result_defaults_to_none(self):
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="do_nothing", platform="social",
            action_args={},
        )
        assert record.action_result is None

    def test_action_result_accepts_dict(self):
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="buy_shares", platform="market",
            action_args={"market_id": "m1", "amount": 100},
            action_result={"cost": 100.0, "price": 0.62, "shares": 161.3},
        )
        assert record.action_result == {"cost": 100.0, "price": 0.62, "shares": 161.3}
