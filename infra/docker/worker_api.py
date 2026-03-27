"""
Lightweight HTTP API running on GPU worker pods.
Receives simulation jobs, runs the MiroFish pipeline, returns results.

Runs alongside vLLM (port 8000) on port 5000.
"""
from flask import Flask, request, jsonify
import subprocess
import json
import os
import threading
from pathlib import Path

app = Flask(__name__)

# Track running job
_current_job = {"status": "idle", "result": None, "error": None}
_lock = threading.Lock()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "job_status": _current_job["status"]})


@app.route("/job", methods=["POST"])
def submit_job():
    """Submit a simulation job. Runs synchronously (blocks until complete)."""
    data = request.json
    seed_text = data.get("seed_text", "")
    goal = data.get("goal", "")
    max_rounds = data.get("max_rounds", 200)

    with _lock:
        if _current_job["status"] == "running":
            return jsonify({"error": "A job is already running"}), 409
        _current_job["status"] = "running"
        _current_job["result"] = None
        _current_job["error"] = None

    try:
        # Write seed to file
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        # Run the pipeline script
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
            timeout=3600,  # 1 hour max
            env={**os.environ},
        )

        if result.returncode != 0:
            error_msg = result.stderr[-2000:] if result.stderr else "Unknown error"
            with _lock:
                _current_job["status"] = "failed"
                _current_job["error"] = error_msg
            return jsonify({
                "status": "failed",
                "error": error_msg,
                "stdout": result.stdout[-1000:],
            }), 500

        # Read results
        results_dir = Path("/tmp/results")
        report = ""
        chat_log = "[]"
        if (results_dir / "report.md").exists():
            report = (results_dir / "report.md").read_text()
        if (results_dir / "chat_log.json").exists():
            chat_log = (results_dir / "chat_log.json").read_text()

        with _lock:
            _current_job["status"] = "completed"
            _current_job["result"] = {"report": report, "chat_log": chat_log}

        return jsonify({
            "status": "completed",
            "report": report,
            "chat_log": chat_log,
        })

    except subprocess.TimeoutExpired:
        with _lock:
            _current_job["status"] = "failed"
            _current_job["error"] = "Job timed out after 1 hour"
        return jsonify({"status": "failed", "error": "Job timed out"}), 500
    except Exception as e:
        with _lock:
            _current_job["status"] = "failed"
            _current_job["error"] = str(e)
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route("/status", methods=["GET"])
def job_status():
    return jsonify(_current_job)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
