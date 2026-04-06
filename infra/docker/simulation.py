"""
Simulation preparation and execution.
"""
from __future__ import annotations

import csv
import json
import os
import time

from constants import TWITTER_STYLE, REDDIT_STYLE


def prepare_simulation(project_id: str, graph_id: str, seed_text: str, goal: str, storage) -> str:
    """
    Step 3: Create simulation state and prepare (entities -> profiles -> config).
    Returns simulation_id.
    """
    from app.services.simulation_manager import SimulationManager

    print("[run_job] Step 3: Creating and preparing simulation...", flush=True)
    sm = SimulationManager()
    state = sm.create_simulation(
        project_id=project_id,
        graph_id=graph_id,
        enable_twitter=True,
        enable_reddit=True,
        enable_polymarket=True,
    )
    simulation_id = state.simulation_id

    def _progress(stage: str, pct: int, msg: str, **_kw: object) -> None:
        print(f"[run_job]   [{stage}] {pct}% — {msg}", flush=True)

    sm.prepare_simulation(
        simulation_id=simulation_id,
        simulation_requirement=goal,
        document_text=seed_text,
        use_llm_for_profiles=True,
        progress_callback=_progress,
        storage=storage,
    )

    print(f"[run_job] Simulation prepared: {simulation_id}", flush=True)
    return simulation_id


def _patch_platform_profiles(simulation_id: str) -> None:
    """Inject platform-specific writing style into agent profiles."""
    from app.services.simulation_runner import SimulationRunner

    sim_dir = os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)

    # Patch Twitter profiles (CSV: user_char column)
    twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
    if os.path.exists(twitter_path):
        rows = []
        with open(twitter_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows.append(header)
            char_idx = header.index('user_char') if 'user_char' in header else 3
            for row in reader:
                if len(row) > char_idx:
                    row[char_idx] = row[char_idx] + TWITTER_STYLE
                rows.append(row)
        with open(twitter_path, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(rows)
        print(f"[run_job] Patched {len(rows) - 1} Twitter profiles with platform style", flush=True)

    # Patch Reddit profiles (JSON: persona field)
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.exists(reddit_path):
        with open(reddit_path, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        for p in profiles:
            if 'persona' in p:
                p['persona'] = p['persona'] + REDDIT_STYLE
        with open(reddit_path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        print(f"[run_job] Patched {len(profiles)} Reddit profiles with platform style", flush=True)


def run_and_wait(simulation_id: str, max_rounds: int, poll_interval: int = 10) -> None:
    """Start the simulation subprocess and block until it finishes."""
    from app.services.simulation_runner import SimulationRunner, RunnerStatus

    print(f"[run_job] Step 4: Starting simulation (max_rounds={max_rounds})...", flush=True)
    SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform="parallel",
        max_rounds=max_rounds,
        enable_cross_platform=True,
    )

    terminal_statuses = {RunnerStatus.COMPLETED, RunnerStatus.STOPPED, RunnerStatus.FAILED}
    timeout = int(os.getenv("JOB_TIMEOUT_SECONDS", "43200"))
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        if elapsed > timeout:
            SimulationRunner.stop_simulation(simulation_id)
            raise TimeoutError(f"Simulation timed out after {timeout}s")

        run_state = SimulationRunner.get_run_state(simulation_id)
        if run_state is None:
            raise RuntimeError("SimulationRunner lost state for simulation_id=" + simulation_id)

        status = run_state.runner_status
        print(
            f"[run_job]   status={status.value}  "
            f"round={run_state.current_round}/{run_state.total_rounds}  "
            f"elapsed={elapsed}s",
            flush=True,
        )

        if status in terminal_statuses:
            break
        time.sleep(poll_interval)

    if run_state.runner_status == RunnerStatus.FAILED:
        raise RuntimeError(f"Simulation failed: {run_state.error}")

    print(f"[run_job] Simulation completed: {run_state.current_round} rounds", flush=True)
