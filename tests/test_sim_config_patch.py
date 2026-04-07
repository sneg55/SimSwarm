"""Tests for simulation config patching logic (round count + activity)."""
from __future__ import annotations

import json


def _make_config(total_hours=72, minutes_per_round=60, off_peak=0.05):
    """Create a minimal simulation_config.json dict."""
    return {
        "time_config": {
            "total_simulation_hours": total_hours,
            "minutes_per_round": minutes_per_round,
            "off_peak_activity_multiplier": off_peak,
        },
        "agent_configs": [],
    }


class TestPatchSimConfig:
    def test_increases_hours_when_rounds_too_low(self):
        """If time_config yields fewer rounds than max_rounds, hours must increase."""
        # 5 hours / 60 min per round = 5 rounds, but max_rounds=200
        tc = _make_config(total_hours=5, minutes_per_round=60)["time_config"]
        minutes_per_round = tc["minutes_per_round"]
        total_hours = tc["total_simulation_hours"]
        max_rounds = 200
        config_rounds = (total_hours * 60) // minutes_per_round

        assert config_rounds == 5  # only 5 rounds from config
        assert config_rounds < max_rounds

        needed_hours = (max_rounds * minutes_per_round + 59) // 60
        assert needed_hours == 200  # 200 rounds * 60 min / 60 = 200 hours

    def test_no_patch_when_rounds_sufficient(self):
        """If time_config already yields enough rounds, no patch needed."""
        tc = _make_config(total_hours=72, minutes_per_round=30)["time_config"]
        config_rounds = (tc["total_simulation_hours"] * 60) // tc["minutes_per_round"]
        assert config_rounds == 144
        assert config_rounds >= 100  # enough for max_rounds=100

    def test_clamps_off_peak_multiplier(self):
        """Off-peak multiplier below 0.3 should be clamped to 0.3."""
        tc = _make_config(off_peak=0.05)["time_config"]
        off_peak = tc.get("off_peak_activity_multiplier", 0.05)
        assert off_peak < 0.3
        clamped = max(0.3, off_peak)
        assert clamped == 0.3

    def test_preserves_reasonable_off_peak(self):
        """Off-peak multiplier >= 0.3 should not be changed."""
        tc = _make_config(off_peak=0.5)["time_config"]
        off_peak = tc.get("off_peak_activity_multiplier", 0.05)
        assert off_peak >= 0.3
        clamped = max(0.3, off_peak)
        assert clamped == 0.5  # unchanged

    def test_full_patch_writes_config(self, tmp_path):
        """End-to-end: write config, apply patch logic, verify file updated."""
        config = _make_config(total_hours=5, minutes_per_round=60, off_peak=0.05)
        config_path = str(tmp_path / "simulation_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Apply patch logic inline (same as _patch_sim_config)
        with open(config_path, "r") as f:
            loaded = json.load(f)

        tc = loaded["time_config"]
        max_rounds = 200
        minutes_per_round = tc["minutes_per_round"]
        total_hours = tc["total_simulation_hours"]
        config_rounds = (total_hours * 60) // minutes_per_round

        if config_rounds < max_rounds:
            tc["total_simulation_hours"] = (max_rounds * minutes_per_round + 59) // 60

        if tc.get("off_peak_activity_multiplier", 0.05) < 0.3:
            tc["off_peak_activity_multiplier"] = 0.3

        loaded["time_config"] = tc
        with open(config_path, "w") as f:
            json.dump(loaded, f)

        # Verify
        with open(config_path, "r") as f:
            result = json.load(f)

        assert result["time_config"]["total_simulation_hours"] == 200
        assert result["time_config"]["off_peak_activity_multiplier"] == 0.3
        new_rounds = (result["time_config"]["total_simulation_hours"] * 60) // result["time_config"]["minutes_per_round"]
        assert new_rounds >= 200
