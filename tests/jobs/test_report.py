"""Tests for ReportRunner (the SaaS-side report orchestrator)."""
from __future__ import annotations

from pathlib import Path

import pytest

from simswarm.llm import LLMResponse
from saas.jobs.report import ReportExhaustedError, ReportRunner

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts" / "small_sim"


def _canned_fetcher(missing: set[str] | None = None):
    missing = missing or set()

    def _fetch(job_id: int, filename: str) -> bytes:
        if filename in missing:
            from saas.storage.minio_download import ArtifactMissingError
            raise ArtifactMissingError(filename)
        return (FIXTURE_DIR / filename).read_bytes()
    return _fetch


class _StubClient:
    """Scripts a sequence of LLMResponse returns for chat()."""
    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls = 0

    async def chat(self, messages, tools=None, temperature=0.7):
        assert self.script, "StubClient ran out of responses"
        self.calls += 1
        return self.script.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_happy_path_returns_markdown_and_findings():
    script = [
        LLMResponse(content="", tool_calls=[{"id": "c1", "name": "get_top_posts", "args": {"limit": 3}}]),
        LLMResponse(content=(
            "## Executive Summary\n"
            "The simulation showed healthy engagement.\n\n"
            "## Key Findings\n"
            "### Finding 1: Core coalition emerged\n"
            "Agents A and B formed a mutual-follow pair.\n\n"
            "## Conclusion\n"
            "High-confidence result.\n"
        ), tool_calls=[]),
    ]
    runner = ReportRunner(
        job_id=42,
        goal="Test goal",
        client=_StubClient(script),
        fetcher=_canned_fetcher(),
    )
    result = await runner.run()
    assert "Executive Summary" in result.report_markdown
    assert "healthy engagement" in result.executive_brief
    assert len(result.findings) == 1
    assert result.findings[0]["title"] == "Finding 1: Core coalition emerged"


@pytest.mark.asyncio
async def test_missing_required_artifact_raises():
    from saas.jobs.report import ReportArtifactsMissingError
    runner = ReportRunner(
        job_id=42,
        goal="Test",
        client=_StubClient([]),
        fetcher=_canned_fetcher(missing={"chat_log.json"}),
    )
    with pytest.raises(ReportArtifactsMissingError):
        await runner.run()


@pytest.mark.asyncio
async def test_exhausted_loop_raises_without_final_markdown():
    tool_only = LLMResponse(
        content="",
        tool_calls=[{"id": "c1", "name": "get_top_posts", "args": {"limit": 1}}],
    )
    runner = ReportRunner(
        job_id=42,
        goal="Test",
        client=_StubClient([tool_only] * 10),
        fetcher=_canned_fetcher(),
    )
    with pytest.raises(ReportExhaustedError):
        await runner.run()
