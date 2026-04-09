"""Tests for ReportGenerator: multi-turn LLM report generation."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from simswarm.llm import LLMClient, LLMResponse
from simswarm.report import Report, ReportGenerator
from tests.engine.report_fixtures import SAMPLE_MARKDOWN, make_result


class TestReportDataclass:
    def test_default_fields(self):
        report = Report()
        assert report.executive_brief == ""
        assert report.findings == []
        assert report.raw_markdown == ""

    def test_fields_assignable(self):
        report = Report(
            executive_brief="Brief text",
            findings=[{"title": "T", "content": "C"}],
            raw_markdown="# Report",
        )
        assert report.executive_brief == "Brief text"
        assert len(report.findings) == 1
        assert report.raw_markdown == "# Report"


class TestReportGeneratorGenerate:
    @pytest.mark.asyncio
    async def test_generate_with_tool_calls_then_markdown_returns_report(self):
        """LLM first returns a tool call, then produces markdown — result has raw_markdown."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[{"name": "get_top_posts", "args": {"limit": 5}}],
            ),
            LLMResponse(content=SAMPLE_MARKDOWN, tool_calls=[]),
        ]

        report = await ReportGenerator(llm=mock_llm).generate(
            make_result(), goal="Predict trade policy outcome"
        )

        assert isinstance(report, Report)
        assert report.raw_markdown == SAMPLE_MARKDOWN

    @pytest.mark.asyncio
    async def test_generate_extracts_brief_from_markdown(self):
        """Brief is extracted from the Executive Summary section."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(content=SAMPLE_MARKDOWN, tool_calls=[])

        report = await ReportGenerator(llm=mock_llm).generate(
            make_result(), goal="Predict trade policy outcome"
        )

        assert report.executive_brief != ""
        assert (
            "polarization" in report.executive_brief
            or "simulation" in report.executive_brief
        )

    @pytest.mark.asyncio
    async def test_generate_extracts_findings_from_markdown(self):
        """Findings list is populated from Key Findings section."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(content=SAMPLE_MARKDOWN, tool_calls=[])

        report = await ReportGenerator(llm=mock_llm).generate(
            make_result(), goal="Predict trade policy outcome"
        )

        assert isinstance(report.findings, list)
        assert len(report.findings) >= 1
        first = report.findings[0]
        assert "title" in first
        assert "content" in first

    @pytest.mark.asyncio
    async def test_generate_stops_after_max_rounds(self):
        """If LLM keeps returning tool calls the loop exits after max rounds."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="",
            tool_calls=[{"name": "get_top_posts", "args": {}}],
        )

        report = await ReportGenerator(llm=mock_llm).generate(
            make_result(), goal="Test goal"
        )

        assert isinstance(report, Report)
        assert mock_llm.chat.call_count <= 5

    @pytest.mark.asyncio
    async def test_generate_calls_llm_with_system_prompt(self):
        """LLM is called with a system message containing goal context."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(content=SAMPLE_MARKDOWN, tool_calls=[])

        await ReportGenerator(llm=mock_llm).generate(
            make_result(), goal="Predict trade policy outcome"
        )

        call_args = mock_llm.chat.call_args
        messages = call_args[0][0] if call_args[0] else call_args.kwargs.get("messages", [])
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        full_system = " ".join(m["content"] for m in system_msgs)
        assert (
            "Predict trade policy outcome" in full_system
            or "report" in full_system.lower()
        )
