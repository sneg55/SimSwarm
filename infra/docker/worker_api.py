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
import json
from pathlib import Path

app = Flask(__name__)

LOG_FILE = Path("/tmp/pipeline.log")

_job = {
    "status": "idle",  # idle, running, completed, failed
    "result": None,
    "error": None,
}
_lock = threading.Lock()


def _upload_sim_data(results_dir, upload_urls):
    """Upload pre-extracted sim data JSON files to MinIO via presigned URLs.

    Retries each file up to 3 times with 2s backoff before giving up.
    Returns True only if ALL files that existed uploaded successfully — under the
    external-report flow, a single failed upload blocks report generation.
    """
    import requests as req
    import time

    attempts_per_file = 3
    backoff_s = 2

    successes = 0
    for filename, url in upload_urls.items():
        filepath = results_dir / filename
        if not filepath.exists():
            print(f"[worker] Skipping {filename} (not produced by pipeline)", flush=True)
            continue
        body = filepath.read_bytes()
        uploaded = False
        for attempt in range(1, attempts_per_file + 1):
            try:
                resp = req.put(
                    url, data=body,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                if resp.status_code in (200, 204):
                    uploaded = True
                    print(f"[worker] Uploaded {filename} ({len(body)} bytes, attempt {attempt})", flush=True)
                    break
                print(
                    f"[worker] Upload {filename} attempt {attempt}: HTTP {resp.status_code}",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[worker] Upload {filename} attempt {attempt}: {exc}",
                    flush=True,
                )
            if attempt < attempts_per_file:
                time.sleep(backoff_s)
        if uploaded:
            successes += 1
        else:
            print(f"[worker] Upload FAILED for {filename} after {attempts_per_file} attempts", flush=True)

    produced = sum(1 for fn in upload_urls if (results_dir / fn).exists())
    print(
        f"[worker] Uploaded {successes}/{produced} sim data files "
        f"(requested {len(upload_urls)})",
        flush=True,
    )
    return successes == produced and produced > 0


def _run_pipeline(seed_text, goal, max_rounds, forecast_days=None, upload_urls=None, target_agents=5):
    """Run MiroFish pipeline in background, stream output to log file."""
    try:
        seed_file = Path("/tmp/seed.txt")
        seed_file.write_text(seed_text)

        # Clear previous log
        LOG_FILE.write_text("")

        with open(LOG_FILE, "w") as log_fh:
            proc = subprocess.Popen(
                [
                    "python3", "-u", "/app/run_job_v2.py",
                    "--seed-file", str(seed_file),
                    "--goal", goal,
                    "--max-rounds", str(max_rounds),
                    "--target-agents", str(target_agents),
                    "--output-dir", "/tmp/results",
                    # Do NOT skip vLLM wait — verify localhost:8000 is actually serving
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

        # Read results — the pod no longer generates report.md or
        # structured_results.json; those are produced by the external-LLM
        # Celery task (saas/jobs/tasks_report.py).
        results_dir = Path("/tmp/results")
        chat_log = "[]"
        graph_data = "{}"
        if (results_dir / "chat_log.json").exists():
            chat_log = (results_dir / "chat_log.json").read_text()
        if (results_dir / "graph_data.json").exists():
            graph_data = (results_dir / "graph_data.json").read_text()

        structured = "{}"

        # Upload rich simulation data files to MinIO (extracted by run_job_v2.py)
        sim_data_uploaded = False
        if upload_urls:
            try:
                sim_data_uploaded = _upload_sim_data(results_dir, upload_urls)
            except Exception as exc:
                print(f"[worker] WARNING: sim data upload failed: {exc}", flush=True)

        with _lock:
            _job["status"] = "completed"
            _job["result"] = {
                "chat_log": chat_log,
                "graph_data": graph_data,
                "structured": structured,
                "sim_data_uploaded": sim_data_uploaded,
            }

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
    forecast_days = data.get("forecast_days")
    upload_urls = data.get("upload_urls")
    target_agents = data.get("target_agents", 5)

    with _lock:
        if _job["status"] == "running":
            return jsonify({"error": "A job is already running"}), 409
        _job["status"] = "running"
        _job["result"] = None
        _job["error"] = None

    LOG_FILE.write_text("")

    thread = threading.Thread(
        target=_run_pipeline,
        args=(seed_text, goal, max_rounds, forecast_days, upload_urls, target_agents),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "accepted"})


@app.route("/status", methods=["GET"])
def job_status():
    """Poll for completion. Returns chat_log + graph_data when done.

    Note: report and structured_results are no longer produced by the pod;
    they are generated by the SaaS-side Celery task (tasks_report.py).
    """
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["chat_log"] = _job["result"]["chat_log"]
            resp["graph_data"] = _job["result"].get("graph_data", "{}")
            resp["structured"] = _job["result"].get("structured", "{}")
            resp["sim_data_uploaded"] = _job["result"].get("sim_data_uploaded", False)
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


@app.route("/partial_chat", methods=["GET"])
def partial_chat():
    """Return the last N chat messages from the in-progress pipeline.

    Reads /tmp/results/chat_log.json which run_job_v2.py writes incrementally.
    Returns [] gracefully if the file doesn't exist or is mid-write (partial JSON).
    """
    tail = request.args.get("tail", 20, type=int)
    path = Path("/tmp/results/chat_log.json")
    if not path.exists():
        return jsonify({"messages": []})
    try:
        data = json.loads(path.read_text())
        messages = data[-tail:] if isinstance(data, list) else []
    except Exception:
        messages = []
    return jsonify({"messages": messages})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
