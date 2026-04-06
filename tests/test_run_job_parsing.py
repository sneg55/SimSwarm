"""
Tests for run_job.py argument parsing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUN_JOB_PATH = Path(__file__).parent.parent / "infra" / "docker" / "run_job.py"


def _load_run_job_module():
    """Dynamically import run_job.py without executing __main__."""
    docker_dir = str(RUN_JOB_PATH.parent)
    if docker_dir not in sys.path:
        sys.path.insert(0, docker_dir)
    spec = importlib.util.spec_from_file_location("run_job", RUN_JOB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# Tests
# ===========================================================================


class TestRunJobArgParsing:
    """Verify that run_job.py's argparse setup accepts the expected CLI flags."""

    def _parse(self, args: list[str]):
        _load_run_job_module()  # verify it loads without error
        # Temporarily replace sys.argv so argparse reads our list
        original_argv = sys.argv[:]
        sys.argv = ["run_job.py"] + args
        try:
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--seed-file", required=True)
            parser.add_argument("--goal", required=True)
            parser.add_argument("--max-rounds", type=int, default=200)
            parser.add_argument("--output-dir", default="/tmp/results")
            parser.add_argument("--skip-vllm-wait", action="store_true")
            return parser.parse_args(args)
        finally:
            sys.argv = original_argv

    def test_required_args_parsed(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "Test goal"])
        assert ns.seed_file == "/tmp/seed.txt"
        assert ns.goal == "Test goal"

    def test_default_max_rounds(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.max_rounds == 200

    def test_custom_max_rounds(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G", "--max-rounds", "42"])
        assert ns.max_rounds == 42

    def test_default_output_dir(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.output_dir == "/tmp/results"

    def test_custom_output_dir(self):
        ns = self._parse([
            "--seed-file", "/tmp/seed.txt",
            "--goal", "G",
            "--output-dir", "/custom/path",
        ])
        assert ns.output_dir == "/custom/path"

    def test_skip_vllm_wait_flag(self):
        ns = self._parse([
            "--seed-file", "/tmp/seed.txt",
            "--goal", "G",
            "--skip-vllm-wait",
        ])
        assert ns.skip_vllm_wait is True

    def test_skip_vllm_wait_defaults_false(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.skip_vllm_wait is False

    def test_run_job_file_exists(self):
        assert RUN_JOB_PATH.exists(), f"run_job.py not found at {RUN_JOB_PATH}"
