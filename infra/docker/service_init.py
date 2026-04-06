"""
Service initialization helpers: wait for Neo4j/vLLM, configure MiroShark.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from constants import VLLM_URL, MIROSHARK_BACKEND


def wait_for_neo4j(timeout: int = 60) -> None:
    """Block until Neo4j responds on the Bolt port."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    start = time.time()
    while time.time() - start < timeout:
        try:
            from neo4j import GraphDatabase
            d = GraphDatabase.driver(uri, auth=(user, password))
            with d.session() as s:
                s.run("RETURN 1")
            d.close()
            print(f"[run_job] Neo4j ready at {uri}", flush=True)
            return
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError(f"Neo4j at {uri} did not respond within {timeout}s")


def wait_for_vllm(timeout: int = 600) -> None:
    """Block until vLLM OpenAI-compatible server responds on /v1/models."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{VLLM_URL}/models", timeout=5)
            if resp.status_code == 200:
                print("[run_job] vLLM server ready", flush=True)
                return
        except requests.ConnectionError:
            pass
        time.sleep(5)
    raise TimeoutError(f"vLLM server did not start within {timeout}s")


def setup_miroshark_config(max_rounds: int) -> None:
    """Write .env for MiroShark and override Config class."""
    env_values = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "not-needed"),
        "LLM_BASE_URL": VLLM_URL,
        "LLM_MODEL_NAME": os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ"),
        "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", ""),
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "openai"),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        "EMBEDDING_BASE_URL": "https://api.openai.com",
        "EMBEDDING_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "EMBEDDING_DIMENSIONS": os.getenv("EMBEDDING_DIMENSIONS", "1536"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OPENAI_API_BASE_URL": VLLM_URL,
        "WONDERWALL_DEFAULT_MAX_ROUNDS": str(max_rounds),
    }

    env_path = Path(MIROSHARK_BACKEND) / ".env"
    env_path.write_text(
        "\n".join(f"{k}={v}" for k, v in env_values.items()) + "\n",
        encoding="utf-8",
    )
    print(f"[run_job] Wrote config to {env_path}", flush=True)


def _apply_config_overrides(max_rounds: int) -> None:
    """Patch Config class after import."""
    from app.config import Config

    Config.LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
    Config.LLM_BASE_URL = VLLM_URL
    Config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ")
    Config.NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    Config.NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    Config.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    Config.EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
    Config.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    Config.EMBEDDING_BASE_URL = "https://api.openai.com"
    Config.EMBEDDING_API_KEY = os.getenv("OPENAI_API_KEY", "")
    Config.EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    Config.WONDERWALL_DEFAULT_MAX_ROUNDS = max_rounds
