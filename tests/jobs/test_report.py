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
            "## Verdict\n"
            "Adoption proceeds with measured friction.\n\n"
            "## Key Findings\n"
            "### slot=industry — Core coalition emerged\n"
            "Agents A and B formed a mutual-follow pair.\n"
            "_Citation: agents A and B mutual-follow._\n\n"
            "## Conclusion\n"
            "High-confidence result.\n"
        ), tool_calls=[]),
    ]
    runner = ReportRunner(
        job_id=42,
        goal="Test goal",
        forecast_days=30,
        client=_StubClient(script),
        fetcher=_canned_fetcher(),
    )
    result = await runner.run()
    assert "Executive Summary" in result.report_markdown
    assert "healthy engagement" in result.executive_brief
    assert result.verdict == "Adoption proceeds with measured friction."
    assert len(result.findings) == 1
    assert result.findings[0]["slot"] == "industry"
    assert result.findings[0]["title"] == "Core coalition emerged"
    assert "mutual-follow pair" in result.findings[0]["body"]
    assert result.findings[0]["citation"] == "agents A and B mutual-follow."


@pytest.mark.asyncio
async def test_findings_parse_full_deck_past_intermediate_h3_headings():
    """Regression for prod sim #112: LLM emitted 4 slotted findings and a
    trailing '## Agent Coalitions' H2, but only the first finding was parsed
    because the Key Findings section-capture lookahead matched '\\n##' inside
    '### slot=...' (since '##' is a prefix of '###').
    """
    script = [
        LLMResponse(content=(
            "## Executive Summary\n"
            "Healthy engagement across all stakeholders.\n\n"
            "## Verdict\n"
            "Compromise prevails.\n\n"
            "## Key Findings\n"
            "### slot=industry — Industry bloc aligns\n"
            "Private-sector actors coalesce around shared framing.\n"
            "_Citation: quotes from JPMorgan and Goldman Sachs._\n\n"
            "### slot=regulator — Regulator signals openness\n"
            "Oversight posture softens mid-phase.\n"
            "_Citation: SEC trajectory declines from 0.08 to 0.02._\n\n"
            "### slot=intermediary — Intermediaries anchor middle\n"
            "Bridge actors carry the compromise.\n"
            "_Citation: Google and Microsoft bridging posts._\n\n"
            "### slot=turning_point — Late-phase pivot\n"
            "Opposition shifts from blocking to shaping.\n"
            "_Citation: Bank Lobbying Coalition late-phase post._\n\n"
            "## Agent Coalitions\n"
            "Two named coalitions surfaced.\n\n"
            "## Market Analysis\n"
            "No speculative trades formed.\n\n"
            "## Conclusion\n"
            "Compromise prevails.\n"
        ), tool_calls=[]),
    ]
    runner = ReportRunner(
        job_id=112,
        goal="Test goal",
        forecast_days=30,
        client=_StubClient(script),
        fetcher=_canned_fetcher(),
    )
    result = await runner.run()
    assert len(result.findings) == 4
    assert [f["slot"] for f in result.findings] == [
        "industry", "regulator", "intermediary", "turning_point",
    ]
    # Each finding should carry its body and citation, not leak into the next.
    assert result.findings[1]["title"] == "Regulator signals openness"
    assert "0.08 to 0.02" in result.findings[1]["citation"]
    assert result.findings[3]["title"] == "Late-phase pivot"


@pytest.mark.asyncio
async def test_missing_required_artifact_raises():
    from saas.jobs.report import ReportArtifactsMissingError
    runner = ReportRunner(
        job_id=42,
        goal="Test",
        forecast_days=30,
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
        forecast_days=30,
        client=_StubClient([tool_only] * 10),
        fetcher=_canned_fetcher(),
    )
    with pytest.raises(ReportExhaustedError):
        await runner.run()
