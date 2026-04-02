"""Tests for live_status column and schema."""
from saas.models.job import SimulationJob
from saas.schemas.jobs import JobResponse


def test_job_model_has_live_status_column():
    """SimulationJob must have a live_status mapped column."""
    cols = [c.key for c in SimulationJob.__mapper__.columns]
    assert "live_status" in cols


def test_job_response_schema_includes_live_status():
    """JobResponse Pydantic schema must include live_status field."""
    fields = JobResponse.model_fields
    assert "live_status" in fields
    assert fields["live_status"].is_required() is False
