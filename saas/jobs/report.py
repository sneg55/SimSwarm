"""SaaS-side report runner: loads MinIO artifacts, runs a tool-calling LLM loop.

Mirrors simswarm.report.ReportGenerator behavior but is driven by MinIO-sourced
ReportArtifacts instead of a live SimulationResult. The prompt template is
reused verbatim from simswarm/prompts/report.j2.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from jinja2 import Environment, FileSystemLoader

from saas.jobs.report_tools_minio import ReportArtifacts, ReportTools
from saas.storage.minio_download import ArtifactMissingError, fetch_artifact
from simswarm.llm import LLMResponse

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 5

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "simswarm" / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

_REQUIRED_ARTIFACTS = ("chat_log.json", "posts.json", "trades.json", "agent_trajectories.json")


class ReportExhaustedError(Exception):
    """The 5-turn loop ended without a final markdown response."""


class ReportArtifactsMissingError(Exception):
    """A required MinIO artifact could not be fetched."""


class _ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = ...,
        temperature: float = ...,
    ) -> LLMResponse: ...
    async def close(self) -> None: ...


@dataclass
class ReportResult:
    report_markdown: str = ""
    executive_brief: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)


class ReportRunner:
    """Orchestrates artifact fetch + multi-turn LLM tool loop for a single job."""

    def __init__(
        self,
        job_id: int,
        goal: str,
        client: _ChatClient,
        fetcher: Callable[[int, str], bytes] = fetch_artifact,
    ) -> None:
        self.job_id = job_id
        self.goal = goal
        self._client = client
        self._fetcher = fetcher

    async def run(self) -> ReportResult:
        artifacts = self._load_artifacts()
        tools = ReportTools(artifacts)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._render_system_prompt()}
        ]
        markdown = ""

        for turn in range(_MAX_ROUNDS):
            response = await self._client.chat(
                messages, tools=ReportTools.tool_schemas()
            )
            if response.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })
                for call in response.tool_calls:
                    result = tools.dispatch(call.get("name", ""), call.get("args", {}))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": result,
                    })
                continue
            markdown = response.content
            break

        if not markdown:
            raise ReportExhaustedError(
                f"Report loop for job {self.job_id} ended without final markdown"
            )

        return ReportResult(
            report_markdown=markdown,
            executive_brief=_extract_brief(markdown),
            findings=_extract_findings(markdown),
        )

    def _load_artifacts(self) -> ReportArtifacts:
        loaded: dict[str, Any] = {}
        for name in _REQUIRED_ARTIFACTS:
            try:
                raw = self._fetcher(self.job_id, name)
            except ArtifactMissingError as exc:
                raise ReportArtifactsMissingError(str(exc)) from exc
            loaded[name] = json.loads(raw.decode("utf-8"))
        return ReportArtifacts(
            chat_log=loaded["chat_log.json"],
            posts=loaded["posts.json"],
            trades=loaded["trades.json"],
            trajectories=loaded["agent_trajectories.json"],
        )

    def _render_system_prompt(self) -> str:
        return _jinja_env.get_template("report.j2").render(goal=self.goal).strip()


def _extract_brief(markdown: str) -> str:
    match = re.search(
        r"##\s+Executive Summary\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _extract_findings(markdown: str) -> list[dict[str, str]]:
    section_match = re.search(
        r"##\s+Key Findings\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []
    findings: list[dict[str, str]] = []
    for block in re.split(r"(?=###\s)", section_match.group(1)):
        block = block.strip()
        if not block:
            continue
        m = re.match(r"###\s+(.+?)\n+(.*)", block, re.DOTALL)
        if m:
            findings.append({"title": m.group(1).strip(), "content": m.group(2).strip()})
    return findings
