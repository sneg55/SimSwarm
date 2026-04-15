"""Coverage for saas.jobs.status stage inference and live extraction."""
from saas.jobs.status import _infer_pipeline_stage, _extract_live_status


def test_stage_report():
    assert _infer_pipeline_stage(["Generating report..."]) == 5


def test_stage_simulation_running():
    assert _infer_pipeline_stage(["Running simulation round=3"]) == 3


def test_stage_preparing():
    assert _infer_pipeline_stage(["preparing environment"]) == 4


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


# --- accumulation / outranking tests ---


def test_preparing_is_stage_4_analyzing():
    """'preparing sim data artifacts' (post-sim extraction) maps to stage 4 Analyzing,
    even when 'Running simulation' still lingers in log_text."""
    log_lines = [
        "[stage] Running simulation",
        "round=15/15",
        "[stage] preparing sim data artifacts",
    ]
    assert _infer_pipeline_stage(log_lines) == 4


def test_running_simulation_without_preparing_is_stage_3_simulating():
    """While only sim markers have fired, stage is 3 (Simulating)."""
    log_lines = [
        "[stage] Running simulation",
        "round=3/15",
    ]
    assert _infer_pipeline_stage(log_lines) == 3


def test_report_outranks_all():
    """'report' must outrank both 'Running simulation' and 'preparing'."""
    log_lines = [
        "[stage] Running simulation",
        "[stage] preparing sim data artifacts",
        "report.generation_started",
    ]
    assert _infer_pipeline_stage(log_lines) == 5


def test_building_is_stage_2_researching():
    """Building entity graph maps to stage 2 (Researching)."""
    log_lines = ["[stage] Generating ontology", "[stage] Building entity graph"]
    assert _infer_pipeline_stage(log_lines) == 2
