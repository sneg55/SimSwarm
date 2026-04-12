"""Coverage for saas.jobs.status stage inference and live extraction."""
from saas.jobs.status import _infer_pipeline_stage, _extract_live_status


def test_stage_report():
    assert _infer_pipeline_stage(["Generating report..."]) == 5


def test_stage_simulation_running():
    assert _infer_pipeline_stage(["Running simulation round=3"]) == 4


def test_stage_preparing():
    assert _infer_pipeline_stage(["preparing environment"]) == 3


def test_stage_building():
    assert _infer_pipeline_stage(["Building ontology"]) == 2


def test_stage_generating_ontology():
    assert _infer_pipeline_stage(["Generating ontology from seed"]) == 1


def test_stage_none():
    assert _infer_pipeline_stage(["something else"]) is None


def test_extract_live_status_finds_rounds():
    lines = [
        "GET /health HTTP/1.1",  # noise filtered
        "round=5 complete",
        "Running simulation round 12",
        "POST /job",  # noise filtered
    ]
    result = _extract_live_status(lines, max_rounds=20)
    assert result["round"] == 12
    assert result["max_rounds"] == 20
    # Noise should be filtered
    assert all("GET /" not in ln and "POST /" not in ln for ln in result["log_lines"])


def test_extract_live_status_short_lines_filtered():
    lines = ["short", "this is a longer log entry that survives filtering"]
    result = _extract_live_status(lines)
    assert "short" not in result["log_lines"]
    assert any("longer" in ln for ln in result["log_lines"])


def test_extract_live_status_no_rounds_or_max():
    result = _extract_live_status(["plain text of enough length here"])
    assert "round" not in result
    assert "max_rounds" not in result
