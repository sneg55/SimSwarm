"""Tests for live_status column and schema."""
from saas.jobs.models import SimulationJob
from saas.jobs.schemas import JobResponse
from saas.jobs.runner import _extract_live_status


def test_job_model_has_live_status_column():
    """SimulationJob must have a live_status mapped column."""
    cols = [c.key for c in SimulationJob.__mapper__.columns]
    assert "live_status" in cols


def test_job_response_schema_includes_live_status():
    """JobResponse Pydantic schema must include live_status field."""
    fields = JobResponse.model_fields
    assert "live_status" in fields
    assert fields["live_status"].is_required() is False


def test_extract_round_from_log_line():
    lines = ["[pipeline] round=47 complete", "[pipeline] Building agent profiles"]
    result = _extract_live_status(lines)
    assert result["round"] == 47


def test_extract_round_variant_spacing():
    lines = ["[pipeline] Running simulation round 12"]
    result = _extract_live_status(lines)
    assert result["round"] == 12


def test_extract_keeps_highest_round():
    lines = ["[pipeline] round=10 complete", "[pipeline] round=47 complete"]
    result = _extract_live_status(lines)
    assert result["round"] == 47


def test_extract_no_round_when_absent():
    lines = ["[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert "round" not in result


def test_extract_filters_http_noise():
    lines = ["GET /health HTTP/1.1", "[pipeline] 12 entities extracted", "POST /job HTTP/1.1"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] 12 entities extracted"]


def test_extract_filters_blank_lines():
    lines = ["", "   ", "[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] Building knowledge graph"]


def test_extract_filters_short_lines():
    lines = ["ok", "[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] Building knowledge graph"]


def test_extract_max_3_log_lines():
    lines = [f"[pipeline] step number {i} complete here" for i in range(10)]
    result = _extract_live_status(lines)
    assert len(result["log_lines"]) <= 3


def test_extract_includes_max_rounds_when_provided():
    result = _extract_live_status(["[pipeline] round=5 done"], max_rounds=200)
    assert result["max_rounds"] == 200


def test_extract_no_max_rounds_when_not_provided():
    result = _extract_live_status(["[pipeline] round=5 done"])
    assert "max_rounds" not in result


def test_extract_no_false_positive_from_surround():
    """Word boundary ensures 'surround=5' is not extracted as round=5."""
    lines = ["[pipeline] surround=5 agents detected here now"]
    result = _extract_live_status(lines)
    assert "round" not in result


def test_extract_empty_input():
    result = _extract_live_status([])
    assert result == {"log_lines": []}
