"""Tests that run_simulation_task calls derive_markets and persists the result."""
from __future__ import annotations

from unittest.mock import MagicMock



class TestRunSimulationTaskDeriver:
    def test_derive_called_after_enrichment_and_persisted(self, monkeypatch):
        from saas.jobs import tasks as tasks_mod

        captured = {}

        def fake_derive(goal, enriched_seed, tier):
            captured["derive_args"] = (goal, enriched_seed, tier)
            return {
                "markets": [{"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"}],
                "source": "llm",
            }

        def fake_update_markets(job_id, markets):
            captured["persisted"] = (job_id, markets)

        class FakeRunner:
            def __init__(self, *a, **k): pass
            async def run(self, config):
                captured["config_markets"] = config.markets_config
                return {"pod_id": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
                        "sim_data_uploaded": True, "report": ""}

        def fake_run_async(coro):
            import asyncio
            return asyncio.new_event_loop().run_until_complete(coro)

        monkeypatch.setattr(tasks_mod, "_get_gpu_provider", lambda: MagicMock())
        monkeypatch.setattr(tasks_mod, "JobRunner", FakeRunner)
        monkeypatch.setattr(tasks_mod, "_run_async", fake_run_async)
        monkeypatch.setattr(tasks_mod, "_update_markets_config", fake_update_markets)
        monkeypatch.setattr(tasks_mod, "_save_job_results", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_update_job_metadata", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_mark_job_failed", lambda **kw: None)
        monkeypatch.setattr(tasks_mod, "_update_enrichment", lambda *a, **k: None)
        monkeypatch.setattr(tasks_mod, "_update_sim_data_available", lambda *a, **k: None)
        monkeypatch.setattr(tasks_mod, "_transition_to_reporting", lambda *a, **k: None)

        # Stub out report task enqueue
        import saas.jobs.tasks_report as tasks_report_mod
        monkeypatch.setattr(tasks_report_mod.generate_report_task, "apply_async", lambda *a, **k: None)

        # Bypass the enrichment branch
        import saas.jobs.enrichment as enrichment_mod
        monkeypatch.setattr(enrichment_mod, "enrich_seed", lambda s, g: None)

        # Patch the deriver at its definition site
        import saas.jobs.market_derivation as md_mod
        monkeypatch.setattr(md_mod, "derive_markets", fake_derive)

        # Call the task's *run* function directly (bypass Celery)
        tasks_mod.run_simulation_task.run(
            job_id=42, user_id="u1",
            seed_text="seed", goal="Will X?", tier="small",
            model_id="m", gpu_type="L40S", max_rounds=15,
            vllm_args="", llm_api_key="",
            enrich_web=False,  # skip enrichment to keep test narrow
        )

        assert captured["derive_args"] == ("Will X?", "seed", "small")
        assert captured["persisted"] == (42, [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"},
        ])
        assert captured["config_markets"] == [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": "r"},
        ]
