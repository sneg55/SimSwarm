"""The pod must emit stage markers and `round=N/M` lines so the Celery
pipeline can infer pipeline_stage and update live_status.round."""
from __future__ import annotations

from unittest.mock import patch


def test_run_pipeline_emits_stage_markers(capsys, tmp_path):
    """run_pipeline prints the four stage markers status.py expects."""
    from infra.docker import run_job_v2

    from simswarm.types import GraphSnapshot, SimulationResult, SimulationState

    # Stub run_simulation so we don't need GPUs / LLMs.
    def _fake_run_simulation(seed_text, goal, max_rounds, entities, target_agents):
        return SimulationResult(
            chat_log=[],
            graph_data=GraphSnapshot(
                nodes=[], edges=[],
                metadata={"total_nodes": 0, "total_edges": 0, "entity_types": []},
            ),
            trajectories={},
            raw_state=SimulationState(
                round=max_rounds, agents={}, environments={}, events=[], snapshots=[],
            ),
        )

    with patch("infra.docker.run_job_v2.get_entities", return_value=[]), \
         patch("infra.docker.run_job_v2.run_simulation", side_effect=lambda *a, **kw: _fake_run_simulation(*a, **kw)):
        run_job_v2.run_pipeline(
            seed_text="x", goal="g", max_rounds=3,
            output_dir=str(tmp_path), target_agents=2,
        )

    captured = capsys.readouterr().out
    assert "Generating ontology" in captured
    assert "Building" in captured
    assert "Running simulation" in captured


def test_run_simulation_emits_round_markers(capsys):
    """Every completed round must print `round=N/M` for live_status parsing."""
    import asyncio
    from types import SimpleNamespace

    from infra.docker import run_job_v2_runner

    class _FakeEngine:
        def __init__(self, *a, **kw):
            pass

        async def run(self, config, on_progress=None):
            if on_progress:
                for r in range(1, config.rounds + 1):
                    await on_progress(r, config.rounds, {})
            from simswarm.types import GraphSnapshot, SimulationResult
            return SimulationResult(
                chat_log=[],
                graph_data=GraphSnapshot(nodes=[], edges=[], metadata={}),
                trajectories={},
            )

    async def _fake_close():
        return None

    fake_client = SimpleNamespace(close=_fake_close)

    with patch("infra.docker.run_job_v2_runner.Engine", _FakeEngine), \
         patch("infra.docker.run_job_v2_runner.LLMClient", lambda **kw: fake_client), \
         patch("infra.docker.run_job_v2_runner.extract_relations", side_effect=lambda *a, **kw: []), \
         patch("infra.docker.run_job_v2_runner.enrich_profiles_with_personas",
               side_effect=lambda profiles, *a, **kw: profiles):
        asyncio.run(run_job_v2_runner.run_simulation(
            seed_text="x", goal="g", max_rounds=3, entities=[], target_agents=1,
        ))

    out = capsys.readouterr().out
    assert "round=1/3" in out
    assert "round=2/3" in out
    assert "round=3/3" in out
