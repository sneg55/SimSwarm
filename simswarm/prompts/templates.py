"""Render Jinja2 prompt templates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from simswarm.types import Entity, Observation

TEMPLATE_DIR = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), keep_trailing_newline=False)


def render_agent_system(entity: Entity, goal: str, stance: str | None = None) -> str:
    template = _env.get_template("agent_system.j2")
    return template.render(entity=entity, goal=goal, stance=stance).strip()


def render_agent_observation(
    observations: list[Observation],
    variables: dict[str, Any] | None = None,
) -> str:
    template = _env.get_template("agent_observation.j2")
    return template.render(observations=observations, variables=variables or {}).strip()
