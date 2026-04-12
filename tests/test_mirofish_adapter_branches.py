"""Branch coverage for saas/adapters/mirofish_adapter.py.

Covers:
- get_simulation_dir path composition
- read_progress: missing file -> None, present file -> parsed dict
- extract_results: missing state file -> None
- extract_results: full happy path reads report + chat log from disk
- extract_results: when reports dir is missing the report_markdown is empty
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from saas.adapters.mirofish_adapter import MiroFishAdapter, SimulationResult


@pytest.fixture
def adapter(tmp_path: Path) -> MiroFishAdapter:
    return MiroFishAdapter(mirofish_path=str(tmp_path))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_get_simulation_dir_path(tmp_path: Path, adapter: MiroFishAdapter):
    p = adapter.get_simulation_dir("sim-123")
    assert p == tmp_path / "backend" / "uploads" / "simulations" / "sim-123"


def test_read_progress_missing_returns_none(adapter: MiroFishAdapter):
    assert adapter.read_progress("does-not-exist") is None


def test_read_progress_reads_file(tmp_path: Path, adapter: MiroFishAdapter):
    state_file = adapter.get_simulation_dir("sim-abc") / "run_state.json"
    _write(state_file, json.dumps({"current_round": 7, "status": "running"}))

    state = adapter.read_progress("sim-abc")
    assert state == {"current_round": 7, "status": "running"}


def test_extract_results_missing_state_returns_none(adapter: MiroFishAdapter):
    assert adapter.extract_results("missing-sim") is None


def test_extract_results_no_reports_dir(tmp_path: Path, adapter: MiroFishAdapter):
    """state file exists but no reports dir — report_markdown remains empty."""
    sim_id = "sim-no-report"
    state_file = adapter.get_simulation_dir(sim_id) / "run_state.json"
    _write(state_file, json.dumps({"current_round": 3}))

    result = adapter.extract_results(sim_id)
    assert isinstance(result, SimulationResult)
    assert result.report_markdown == ""
    assert result.chat_log == []
    assert result.total_rounds == 3
    assert result.total_actions == 0


def test_extract_results_full_happy_path(tmp_path: Path, adapter: MiroFishAdapter):
    """Report markdown and chat log are assembled from sections and actions.jsonl."""
    sim_id = "sim-happy"
    sim_dir = adapter.get_simulation_dir(sim_id)

    # run state
    _write(sim_dir / "run_state.json", json.dumps({"current_round": 12}))

    # Report under reports/<whatever>/ with matching simulation_id in meta.json
    report_dir = tmp_path / "backend" / "uploads" / "reports" / "report-xyz"
    _write(report_dir / "meta.json", json.dumps({"simulation_id": sim_id}))
    _write(report_dir / "section_01.md", "# Intro\nThis is the intro.")
    _write(report_dir / "section_02.md", "## Findings\nMarkets will rise.")

    # chat logs on both platforms
    _write(
        sim_dir / "twitter" / "actions.jsonl",
        json.dumps({"agent": "A1", "message": "hi"}) + "\n" +
        json.dumps({"agent": "A2", "message": "hello"}),
    )
    _write(
        sim_dir / "reddit" / "actions.jsonl",
        json.dumps({"agent": "A3", "message": "post"}),
    )

    result = adapter.extract_results(sim_id)
    assert result is not None
    assert "# Intro" in result.report_markdown
    assert "Findings" in result.report_markdown
    assert result.total_rounds == 12
    assert len(result.chat_log) == 3
    assert result.total_actions == 3


def test_extract_results_ignores_non_matching_reports(tmp_path: Path, adapter: MiroFishAdapter):
    """A reports directory exists but no meta.json ties to our sim_id."""
    sim_id = "sim-unmatched"
    _write(adapter.get_simulation_dir(sim_id) / "run_state.json", json.dumps({"current_round": 1}))

    # Report dir for a *different* simulation
    other = tmp_path / "backend" / "uploads" / "reports" / "report-other"
    _write(other / "meta.json", json.dumps({"simulation_id": "some-other-sim"}))
    _write(other / "section_01.md", "# Not ours")

    result = adapter.extract_results(sim_id)
    assert result is not None
    assert result.report_markdown == ""
