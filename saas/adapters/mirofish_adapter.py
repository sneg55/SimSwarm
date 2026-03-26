"""
Thin adapter wrapping MiroFish engine services.

This adapter does NOT call MiroFish's Flask HTTP endpoints.
Instead, it invokes the engine via subprocess (matching how MiroFish
internally runs simulations via scripts/run_parallel_simulation.py).

The adapter:
1. Builds the environment config MiroFish expects
2. Launches the simulation subprocess
3. Monitors progress via file-system IPC (run_state.json)
4. Extracts results from the file-based output
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MiroFishConfig:
    """Configuration injected into MiroFish engine at runtime."""
    llm_api_key: str
    llm_base_url: str
    llm_model_name: str
    zep_api_key: str
    seed_text: str
    goal: str
    max_rounds: int = 200

    def to_env_dict(self) -> dict[str, str]:
        return {
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": self.llm_base_url,
            "LLM_MODEL_NAME": self.llm_model_name,
            "ZEP_API_KEY": self.zep_api_key,
            "OASIS_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
        }


@dataclass
class SimulationResult:
    """Extracted results from a completed MiroFish simulation."""
    report_markdown: str
    chat_log: list[dict[str, Any]]
    total_rounds: int
    total_actions: int


class MiroFishAdapter:
    """Wraps MiroFish engine for use by the SaaS job workers."""

    def __init__(self, mirofish_path: str):
        self.mirofish_path = Path(mirofish_path)

    def build_env(self, config: MiroFishConfig) -> dict[str, str]:
        """Build environment variables dict for MiroFish subprocess."""
        env = os.environ.copy()
        env.update(config.to_env_dict())
        return env

    def get_simulation_dir(self, simulation_id: str) -> Path:
        """Return the file-system path where MiroFish stores sim data."""
        return self.mirofish_path / "backend" / "uploads" / "simulations" / simulation_id

    def read_progress(self, simulation_id: str) -> dict[str, Any] | None:
        """Read current simulation progress from run_state.json."""
        state_file = self.get_simulation_dir(simulation_id) / "run_state.json"
        if not state_file.exists():
            return None
        return json.loads(state_file.read_text())

    def extract_results(self, simulation_id: str) -> SimulationResult | None:
        """Extract final results from completed simulation files."""
        sim_dir = self.get_simulation_dir(simulation_id)
        state_file = sim_dir / "run_state.json"

        if not state_file.exists():
            return None

        state = json.loads(state_file.read_text())

        # Read report from reports directory
        report_markdown = ""
        reports_dir = self.mirofish_path / "backend" / "uploads" / "reports"
        if reports_dir.exists():
            for report_dir in reports_dir.iterdir():
                meta_file = report_dir / "meta.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text())
                    if meta.get("simulation_id") == simulation_id:
                        sections = sorted(report_dir.glob("section_*.md"))
                        report_markdown = "\n\n".join(s.read_text() for s in sections)
                        break

        # Read agent chat logs from actions.jsonl
        chat_log = []
        for platform in ["twitter", "reddit"]:
            actions_file = sim_dir / platform / "actions.jsonl"
            if actions_file.exists():
                for line in actions_file.read_text().strip().split("\n"):
                    if line:
                        chat_log.append(json.loads(line))

        return SimulationResult(
            report_markdown=report_markdown,
            chat_log=chat_log,
            total_rounds=state.get("current_round", 0),
            total_actions=len(chat_log),
        )
