---
sidebar_label: Sweeps
---

# Parameter Sweeps

A **scenario sweep** runs the same base simulation across a grid of scenario-variable values
to compare outcomes. The mechanism is small and lives in `simswarm/sweep.py`, driven by
`Engine.run_sweep`.

## The sweep config

```python
@dataclass
class ScenarioSweep:
    base_config: SimulationConfig
    vary: dict[str, list[Any]] = field(default_factory=dict)
```

`vary` maps a scenario-variable name to the list of values to try for it.

## Expanding to configs

`generate_sweep_configs(sweep)` produces the Cartesian product of the varied values:

```python
def generate_sweep_configs(sweep) -> list[tuple[dict[str, Any], SimulationConfig]]:
```

- If `vary` is empty, it returns a single `({}, deepcopy(base_config))` — one run, unchanged.
- Otherwise it takes `itertools.product` over the value lists. For each combination it
  builds a `key` dict (`{var_name: value}`), deep-copies the base config, and **updates**
  `config.variables` with that key. The scenario variables then flow into each run's
  observations (the engine appends a `scenario` observation rendering `config.variables`),
  so agents actually see the swept parameters.

Each returned tuple is `(key, config)`, where `key` identifies which combination produced
that config. Because every config is a deep copy, runs don't share mutable state.

## Running a sweep

```python
async def run_sweep(self, sweep, on_progress=None) -> list[tuple[dict, SimulationResult]]:
    configs = generate_sweep_configs(sweep)
    results = []
    for key, config in configs:
        result = await self.run(config, on_progress=on_progress)
        results.append((key, result))
    return results
```

`Engine.run_sweep` expands the sweep and runs each config **sequentially** (one full
`Engine.run` per combination), returning a list of `(key, SimulationResult)` pairs. The
`on_progress` callback, if supplied, is forwarded into each run. Note the runs are not
parallelized at the sweep level — concurrency applies *within* a run via the per-round agent
semaphore (see [Architecture](architecture.md)), not *across* sweep combinations.

## Example

```python
sweep = ScenarioSweep(
    base_config=cfg,
    vary={"tariff_rate": [0.0, 0.1, 0.25], "stimulus": ["none", "broad"]},
)
results = await engine.run_sweep(sweep)   # 3 x 2 = 6 runs
```

Each of the 6 `SimulationResult`s is paired with its key, e.g.
`{"tariff_rate": 0.1, "stimulus": "broad"}`, ready for side-by-side comparison.
