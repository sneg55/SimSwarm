"""Service initialization helpers: wait for Neo4j and vLLM."""
from __future__ import annotations

import os
import time

import requests

from constants import VLLM_URL


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
            print(f"[worker] Neo4j ready at {uri}", flush=True)
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
                print("[worker] vLLM server ready", flush=True)
                return
        except requests.ConnectionError:
            pass
        time.sleep(5)
    raise TimeoutError(f"vLLM server did not start within {timeout}s")
