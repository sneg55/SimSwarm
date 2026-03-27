"""
Lightweight HTTP API running on GPU worker pods.
Receives simulation jobs, runs MiroFish pipeline in background thread, results via polling.

Runs alongside vLLM (port 8000) on port 5000.

Flow:
  POST /job   -> starts pipeline in background, returns {"status": "accepted"} immediately
  GET /status -> poll until status is "completed" or "failed", includes report + chat_log
  GET /health -> liveness check
"""
from flask import Flask, request, jsonify
import subprocess
import os
import threading
from pathlib import Path

app = Flask(__name__)

_job = {
    "status": "idle",  # idle, running, completed, failed
    "result": None,
    "error": None,
    "stdout": None,
}
_lock = threading.Lock()


def _run_pipeline(seed_text, goal, max_rounds):
    """Run the MiroFish pipeline in a background thread."""
    try:
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        result = subprocess.run(
            [
                "python3", "/app/run_job.py",
                "--seed-file", str(seed_file),
                "--goal", goal,
                "--max-rounds", str(max_rounds),
                "--output-dir", "/tmp/results",
            ],
            capture_output=True,
            text=True,
            timeout=3600,
            env={**os.environ},
        )

        if result.returncode != 0:
            with _lock:
                _job["status"] = "failed"
                _job["error"] = result.stderr[-3000:] if result.stderr else "Unknown error"
                _job["stdout"] = result.stdout[-3000:] if result.stdout else ""
            return

        results_dir = Path("/tmp/results")
        report = ""
        chat_log = "[]"
        if (results_dir / "report.md").exists():
            report = (results_dir / "report.md").read_text()
        if (results_dir / "chat_log.json").exists():
            chat_log = (results_dir / "chat_log.json").read_text()

        with _lock:
            _job["status"] = "completed"
            _job["result"] = {"report": report, "chat_log": chat_log}
            _job["stdout"] = result.stdout[-3000:] if result.stdout else ""

    except subprocess.TimeoutExpired:
        with _lock:
            _job["status"] = "failed"
            _job["error"] = "Job timed out after 1 hour"
    except Exception as e:
        with _lock:
            _job["status"] = "failed"
            _job["error"] = str(e)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "job_status": _job["status"]})


@app.route("/job", methods=["POST"])
def submit_job():
    """Submit a job — returns immediately, pipeline runs in background thread."""
    data = request.json or {}
    seed_text = data.get("seed_text", "")
    goal = data.get("goal", "")
    max_rounds = data.get("max_rounds", 200)

    with _lock:
        if _job["status"] == "running":
            return jsonify({"error": "A job is already running"}), 409
        _job["status"] = "running"
        _job["result"] = None
        _job["error"] = None
        _job["stdout"] = None

    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "accepted"})


@app.route("/status", methods=["GET"])
def job_status():
    """Poll for job completion. Returns report + chat_log when done."""
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["report"] = _job["result"]["report"]
            resp["chat_log"] = _job["result"]["chat_log"]
        if _job["status"] == "failed":
            resp["error"] = _job["error"]
            resp["stdout"] = _job["stdout"]
        return jsonify(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
