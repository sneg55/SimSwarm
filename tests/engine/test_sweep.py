"""Test scenario sweep: config generation and variable combinatorics."""
from __future__ import annotations

from simswarm.sweep import ScenarioSweep, generate_sweep_configs
from simswarm.types import SimulationConfig


def _base_config() -> SimulationConfig:
    return SimulationConfig(
        seed_text="Test seed",
        goal="Test goal",
        entities=[],
        environments=[],
        rounds=10,
        concurrency=4,
        variables={"policy": "default", "timeline": "moderate"},
    )


class TestConfigGeneration:
    def test_single_variable_generates_correct_count(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b", "c"]},
        )
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 3

    def test_two_variables_generate_cartesian_product(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={
                "policy": ["equity", "supply"],
                "timeline": ["slow", "fast"],
            },
        )
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 4

    def test_generated_configs_have_correct_variables(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b"]},
        )
        configs = generate_sweep_configs(sweep)
        policies = {c.variables["policy"] for _, c in configs}
        assert policies == {"a", "b"}

    def test_configs_keyed_by_variable_tuple(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a"], "timeline": ["slow"]},
        )
        configs = generate_sweep_configs(sweep)
        key, config = configs[0]
        assert key == {"policy": "a", "timeline": "slow"}

    def test_base_config_unchanged_variables_preserved(self):
        base = _base_config()
        base.variables["extra"] = "keep_me"
        sweep = ScenarioSweep(base_config=base, vary={"policy": ["x"]})
        configs = generate_sweep_configs(sweep)
        _, config = configs[0]
        assert config.variables["extra"] == "keep_me"
        assert config.variables["policy"] == "x"

    def test_empty_vary_returns_single_base_config(self):
        sweep = ScenarioSweep(base_config=_base_config(), vary={})
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 1


class TestSweepCopyIsolation:
    def test_configs_are_independent_copies(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b"]},
        )
        configs = generate_sweep_configs(sweep)
        _, config_a = configs[0]
        _, config_b = configs[1]
        config_a.variables["injected"] = True
        assert "injected" not in config_b.variables
