"""Prevent silent regressions where the report prompt drops a section.

The SimulationResults Story view + SharedResult expect five sections in
the LLM-generated markdown. This test asserts the prompt template lists
all five explicitly."""
from __future__ import annotations

from pathlib import Path


REPORT_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "simswarm" / "prompts" / "report.j2"
)


def test_report_prompt_lists_all_five_sections():
    text = REPORT_TEMPLATE.read_text(encoding="utf-8")
    for heading in (
        "## Executive Summary",
        "## Key Findings",
        "## Agent Coalitions",
        "## Market Analysis",
        "## Conclusion",
    ):
        assert heading in text, f"Report prompt missing {heading!r}"
