"""Unit tests for the pod-side /partial_chat endpoint.

The endpoint used to return `[]` for the entire sim because it read from
chat_log.json — which only exists once write_results() runs at sim end.
The fix writes chat_log.json.partial after each round, and /partial_chat
now serves the partial file until the final one appears.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


WORKER_API_PATH = Path(__file__).parent.parent / "infra" / "docker" / "worker_api.py"


def _load_worker_api():
    spec = importlib.util.spec_from_file_location("worker_api_pc", WORKER_API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.app.config["TESTING"] = True
    return mod


def _patch_paths(mod, partial, final):
    """Redirect the two hard-coded chat-log paths to the test tmp files."""
    orig = mod.Path

    def _path(p):
        if str(p) == "/tmp/results/chat_log.json.partial":
            return partial
        if str(p) == "/tmp/results/chat_log.json":
            return final
        return orig(p)

    mod.Path = _path
    return orig


def test_partial_chat_reads_partial_file_during_run(tmp_path):
    """While the sim is still running, chat_log.json doesn't exist yet — the
    endpoint must fall back to chat_log.json.partial so the live UI populates."""
    partial = tmp_path / "chat_log.json.partial"
    partial.write_text('[{"agent":"a1","content":"hello","role":"assistant"}]')
    final = tmp_path / "chat_log.json"

    mod = _load_worker_api()
    orig = _patch_paths(mod, partial, final)
    try:
        resp = mod.app.test_client().get("/partial_chat?tail=10")
    finally:
        mod.Path = orig

    assert resp.status_code == 200
    assert resp.get_json()["messages"] == [
        {"agent": "a1", "content": "hello", "role": "assistant"}
    ]


def test_partial_chat_prefers_final_file_when_complete(tmp_path):
    """Once the sim finishes, chat_log.json exists and wins over the
    partial (which may still be lying around from the last mid-run snapshot)."""
    partial = tmp_path / "chat_log.json.partial"
    partial.write_text('[{"agent":"stale","content":"old"}]')
    final = tmp_path / "chat_log.json"
    final.write_text('[{"agent":"final","content":"done"}]')

    mod = _load_worker_api()
    orig = _patch_paths(mod, partial, final)
    try:
        resp = mod.app.test_client().get("/partial_chat?tail=10")
    finally:
        mod.Path = orig

    assert resp.get_json()["messages"] == [{"agent": "final", "content": "done"}]


def test_partial_chat_returns_empty_when_neither_file_exists(tmp_path):
    """Pre-simulation phase: no partial, no final → empty messages list."""
    partial = tmp_path / "chat_log.json.partial"
    final = tmp_path / "chat_log.json"

    mod = _load_worker_api()
    orig = _patch_paths(mod, partial, final)
    try:
        resp = mod.app.test_client().get("/partial_chat?tail=10")
    finally:
        mod.Path = orig

    assert resp.get_json()["messages"] == []
