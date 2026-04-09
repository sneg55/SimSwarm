"""Lean report generator with tool access over SimulationResult.

Uses the smart LLM client for multi-turn report writing.

Split:
  simswarm.report_tools  — ReportTools class and _adapt_log helper
  simswarm.report        — Report dataclass, ReportGenerator, markdown parsers
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from simswarm.llm import LLMClient, LLMResponse
from simswarm.report_tools import ReportTools
from simswarm.types import SimulationResult

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

_MAX_ROUNDS = 5

# Re-export so callers can do `from simswarm.report import ReportTools`
__all__ = ["Report", "ReportGenerator", "ReportTools"]


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class Report:
    executive_brief: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)
    raw_markdown: str = ""


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Multi-turn LLM report generator."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(self, result: SimulationResult, goal: str) -> Report:
        """Run the multi-turn tool loop, then build and return a Report."""
        tools = ReportTools(result)
        messages: list[dict] = [
            {"role": "system", "content": _render_system_prompt(goal)}
        ]

        markdown = ""
        for _ in range(_MAX_ROUNDS):
            response: LLMResponse = await self._llm.chat(
                messages,
                tools=ReportTools.tool_schemas(),
            )

            if response.tool_calls:
                messages.append({"role": "assistant", "content": response.content or ""})
                for call in response.tool_calls:
                    tool_result = tools.dispatch(call["name"], call.get("args", {}))
                    messages.append({"role": "tool", "content": tool_result})
            else:
                markdown = response.content
                break

        return Report(
            executive_brief=_extract_brief(markdown),
            findings=_extract_findings(markdown),
            raw_markdown=markdown,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _render_system_prompt(goal: str) -> str:
    return _jinja_env.get_template("report.j2").render(goal=goal).strip()


def _extract_brief(markdown: str) -> str:
    """Parse the Executive Summary paragraph from the markdown."""
    match = re.search(
        r"##\s+Executive Summary\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _extract_findings(markdown: str) -> list[dict[str, str]]:
    """Parse Key Findings subsections into list of {title, content} dicts."""
    section_match = re.search(
        r"##\s+Key Findings\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []

    findings = []
    for block in re.split(r"(?=###\s)", section_match.group(1)):
        block = block.strip()
        if not block:
            continue
        m = re.match(r"###\s+(.+?)\n+(.*)", block, re.DOTALL)
        if m:
            findings.append({"title": m.group(1).strip(), "content": m.group(2).strip()})
    return findings
