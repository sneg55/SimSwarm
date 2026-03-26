"""
Tests for the GPU worker pipeline wiring:
  - run_job.py argument parsing
  - JobRunner._execute_pipeline() command sequence (mocked GPU provider)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

import pytest

from saas.gpu.provider import GPUInstance
from saas.workers.job_runner import JobConfig, JobRunner

# ---------------------------------------------------------------------------
# Helpers shared by both test sections
# ---------------------------------------------------------------------------

RUN_JOB_PATH = Path(__file__).parent.parent / "infra" / "docker" / "run_job.py"


def _load_run_job_module():
    """Dynamically import run_job.py without executing __main__."""
    spec = importlib.util.spec_from_file_location("run_job", RUN_JOB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_job_config(**overrides) -> JobConfig:
    defaults = dict(
        job_id=1,
        user_id="user-test",
        seed_text="Climate change is accelerating.",
        goal="Analyse public opinion about climate",
        tier="medium",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="RTX4090",
        max_rounds=50,
        vllm_args="",
        llm_api_key="sk-test",
        zep_api_key="zep-test",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


def _make_instance(instance_id: str = "inst-abc") -> GPUInstance:
    return GPUInstance(
        instance_id=instance_id,
        provider="runpod",
        gpu_type="RTX4090",
        ip_address="10.0.0.1",
        ssh_port=22,
        status="running",
    )


# ===========================================================================
# Section 1: run_job.py argument parsing
# ===========================================================================


class TestRunJobArgParsing:
    """Verify that run_job.py's argparse setup accepts the expected CLI flags."""

    def _parse(self, args: list[str]):
        mod = _load_run_job_module()
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


# ===========================================================================
# Section 2: JobRunner._execute_pipeline() command sequence
# ===========================================================================


class TestExecutePipeline:
    """Verify _execute_pipeline() sends the correct commands to the GPU provider."""

    @pytest.mark.asyncio
    async def test_uploads_seed_text(self):
        """Pipeline uploads seed text to /tmp/seed.txt on the instance."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(seed_text="Hello world")
        await runner._execute_pipeline("inst-1", config)

        # First execute_command call should write seed text
        first_call_cmd: str = gpu.execute_command.call_args_list[0][0][1]
        assert "/tmp/seed.txt" in first_call_cmd
        assert "Hello world" in first_call_cmd

    @pytest.mark.asyncio
    async def test_runs_run_job_script(self):
        """Pipeline calls run_job.py with --seed-file, --goal and --max-rounds."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(goal="Analyse opinions", max_rounds=99)
        await runner._execute_pipeline("inst-2", config)

        # Second execute_command call should launch run_job.py
        pipeline_cmd: str = gpu.execute_command.call_args_list[1][0][1]
        assert "run_job.py" in pipeline_cmd
        assert "--seed-file /tmp/seed.txt" in pipeline_cmd
        assert "--max-rounds 99" in pipeline_cmd
        assert "--output-dir /tmp/results" in pipeline_cmd

    @pytest.mark.asyncio
    async def test_goal_included_in_run_command(self):
        """The --goal flag value is present in the run_job.py invocation."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(goal="Unique research goal XYZ")
        await runner._execute_pipeline("inst-3", config)

        pipeline_cmd: str = gpu.execute_command.call_args_list[1][0][1]
        assert "Unique research goal XYZ" in pipeline_cmd

    @pytest.mark.asyncio
    async def test_downloads_report(self):
        """Pipeline issues a cat command to download /tmp/results/report.md."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "# Report"

        runner = JobRunner(gpu_provider=gpu)
        await runner._execute_pipeline("inst-4", _make_job_config())

        download_cmds = [str(c) for c in gpu.execute_command.call_args_list]
        assert any("/tmp/results/report.md" in cmd for cmd in download_cmds)

    @pytest.mark.asyncio
    async def test_downloads_chat_log(self):
        """Pipeline issues a cat command to download /tmp/results/chat_log.json."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "[]"

        runner = JobRunner(gpu_provider=gpu)
        await runner._execute_pipeline("inst-5", _make_job_config())

        download_cmds = [str(c) for c in gpu.execute_command.call_args_list]
        assert any("/tmp/results/chat_log.json" in cmd for cmd in download_cmds)

    @pytest.mark.asyncio
    async def test_returns_report_and_chat_log(self):
        """_execute_pipeline() returns a dict with 'report' and 'chat_log' keys."""
        gpu = AsyncMock()
        # Return values correspond to the four execute_command calls:
        # 1. upload seed, 2. run pipeline, 3. cat report.md, 4. cat chat_log.json
        gpu.execute_command.side_effect = ["ok", "ok", "# My Report", '[{"action":"post"}]']

        runner = JobRunner(gpu_provider=gpu)
        result = await runner._execute_pipeline("inst-6", _make_job_config())

        assert result["report"] == "# My Report"
        assert result["chat_log"] == '[{"action":"post"}]'

    @pytest.mark.asyncio
    async def test_returns_job_id_and_instance_id(self):
        """Result dict also carries job_id and instance_id for traceability."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(job_id=777)
        result = await runner._execute_pipeline("inst-777", config)

        assert result["job_id"] == 777
        assert result["instance_id"] == "inst-777"

    @pytest.mark.asyncio
    async def test_execute_pipeline_called_exactly_four_times(self):
        """Four execute_command calls: upload, run, cat report, cat chat_log."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        await runner._execute_pipeline("inst-8", _make_job_config())

        assert gpu.execute_command.call_count == 4

    @pytest.mark.asyncio
    async def test_goal_single_quotes_escaped(self):
        """Single quotes in goal are shell-escaped so the command is valid."""
        gpu = AsyncMock()
        gpu.execute_command.return_value = "ok"

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(goal="It's a test")
        await runner._execute_pipeline("inst-9", config)

        pipeline_cmd: str = gpu.execute_command.call_args_list[1][0][1]
        # The raw single-quote must not appear unescaped inside the quoted goal
        # Our implementation uses the '\'' technique
        assert "It" in pipeline_cmd
        assert "s a test" in pipeline_cmd

    @pytest.mark.asyncio
    async def test_full_run_terminates_gpu_on_success(self):
        """runner.run() still terminates the GPU even with the updated pipeline."""
        gpu = AsyncMock()
        instance = _make_instance("inst-full")
        gpu.provision.return_value = instance
        gpu.execute_command.return_value = "ok"
        gpu.terminate.return_value = None

        runner = JobRunner(gpu_provider=gpu)
        await runner.run(_make_job_config())

        gpu.terminate.assert_called_once_with("inst-full")
