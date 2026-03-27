"""
GPU Worker HTTP API — runs on RunPod pods alongside vLLM.

Endpoints:
  GET  /health  -> liveness + vLLM readiness check
  POST /job     -> starts pipeline in background, returns immediately
  GET  /status  -> poll for completion, includes report + chat_log when done
  GET  /logs    -> real-time stdout/stderr from the running pipeline
"""
from flask import Flask, request, jsonify
import subprocess
import os
import threading
from pathlib import Path

app = Flask(__name__)

LOG_FILE = Path("/tmp/pipeline.log")

_job = {
    "status": "idle",  # idle, running, completed, failed
    "result": None,
    "error": None,
}
_lock = threading.Lock()


def _run_pipeline(seed_text, goal, max_rounds):
    """Run MiroFish pipeline in background, stream output to log file."""
    try:
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        # Clear previous log
        LOG_FILE.write_text("")

        with open(LOG_FILE, "w") as log_fh:
            proc = subprocess.Popen(
                [
                    "python3", "-u", "/app/run_job.py",
                    "--seed-file", str(seed_file),
                    "--goal", goal,
                    "--max-rounds", str(max_rounds),
                    "--output-dir", "/tmp/results",
                    "--skip-vllm-wait",
                ],
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env={**os.environ},
            )
            proc.wait(timeout=3600)

        log_content = LOG_FILE.read_text()

        if proc.returncode != 0:
            with _lock:
                _job["status"] = "failed"
                _job["error"] = log_content[-5000:]
            return

        # Read results
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

    except subprocess.TimeoutExpired:
        proc.kill()
        with _lock:
            _job["status"] = "failed"
            _job["error"] = "Job timed out after 1 hour"
    except Exception as e:
        with _lock:
            _job["status"] = "failed"
            _job["error"] = str(e)


@app.route("/health", methods=["GET"])
def health():
    """Liveness + vLLM readiness check."""
    import requests as req
    vllm_ok = False
    try:
        r = req.get("http://localhost:8000/v1/models", timeout=3)
        vllm_ok = r.status_code == 200
    except Exception:
        pass
    return jsonify({
        "status": "ok" if vllm_ok else "waiting_for_vllm",
        "vllm_ready": vllm_ok,
        "job_status": _job["status"],
    }), 200 if vllm_ok else 503


@app.route("/job", methods=["POST"])
def submit_job():
    """Start pipeline in background. Returns immediately."""
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

    LOG_FILE.write_text("")

    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "accepted"})


@app.route("/status", methods=["GET"])
def job_status():
    """Poll for completion. Returns report + chat_log when done."""
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["report"] = _job["result"]["report"]
            resp["chat_log"] = _job["result"]["chat_log"]
        if _job["status"] == "failed":
            resp["error"] = _job["error"]
    return jsonify(resp)


@app.route("/logs", methods=["GET"])
def logs():
    """Real-time logs from both vLLM and the pipeline."""
    tail = request.args.get("tail", 100, type=int)
    source = request.args.get("source", "all")  # all, pipeline, vllm

    lines = []
    if source in ("all", "vllm"):
        vllm_log = Path("/tmp/vllm.log")
        if vllm_log.exists():
            for line in vllm_log.read_text().splitlines()[-tail:]:
                lines.append(f"[vllm] {line}")

    if source in ("all", "pipeline"):
        if LOG_FILE.exists():
            for line in LOG_FILE.read_text().splitlines()[-tail:]:
                lines.append(f"[pipeline] {line}")

    return jsonify({
        "lines": lines[-tail:],
        "total_lines": len(lines),
        "job_status": _job["status"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
