"""Scenario sweep: generate config combinations for parameter variation."""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any

from simswarm.types import SimulationConfig


@dataclass
class ScenarioSweep:
    base_config: SimulationConfig
    vary: dict[str, list[Any]] = field(default_factory=dict)


def generate_sweep_configs(
    sweep: ScenarioSweep,
) -> list[tuple[dict[str, Any], SimulationConfig]]:
    if not sweep.vary:
        return [({}, copy.deepcopy(sweep.base_config))]

    var_names = list(sweep.vary.keys())
    var_values = [sweep.vary[name] for name in var_names]

    results = []
    for combo in itertools.product(*var_values):
        key = dict(zip(var_names, combo))
        config = copy.deepcopy(sweep.base_config)
        config.variables.update(key)
        results.append((key, config))

    return results
