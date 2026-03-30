"""Graphiti + Kuzu singleton for MiroFish shadow modules."""
from __future__ import annotations

import asyncio
import logging
import os
import threading

logger = logging.getLogger(__name__)

_instance = None
_entity_types = None
_edge_types = None
_edge_type_map = None
_loop = None
_thread = None
_init_lock = threading.Lock()


def _get_loop():
    """Get or create a persistent event loop for all graphiti operations.

    Kuzu's AsyncConnection is bound to the event loop that created it.
    Using asyncio.run() (which creates a new loop each call) breaks the
    connection on subsequent calls. A persistent loop solves this.
    """
    global _loop, _thread
    if _loop is not None and _loop.is_running():
        return _loop

    _loop = asyncio.new_event_loop()

    def _run_loop():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=_run_loop, daemon=True)
    _thread.start()
    return _loop


def _run(coro):
    """Run async coroutine on the persistent graphiti event loop.

    All graphiti operations must run on the same event loop because Kuzu's
    AsyncConnection is bound to the loop that created it.
    """
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=300)  # 5 min timeout


async def get_graphiti_instance():
    """Lazy singleton — creates Graphiti with Kuzu in-memory + vLLM + OpenAI embedder."""
    global _instance
    with _init_lock:
        if _instance is not None:
            return _instance

    from graphiti_core import Graphiti
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    driver = KuzuDriver(db=":memory:")
    # KuzuDriver doesn't set _database (base GraphDriver field) — patch it
    if not hasattr(driver, '_database'):
        driver._database = ':memory:'

    llm_client = OpenAIGenericClient(
        config=LLMConfig(
            api_key=os.getenv("LLM_API_KEY", "not-needed"),
            model=os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct-AWQ"),
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
            temperature=0,
        ),
    )

    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
        )
    )

    with _init_lock:
        _instance = Graphiti(
            graph_driver=driver,
            llm_client=llm_client,
            embedder=embedder,
        )
    logger.info("Graphiti + Kuzu initialized (in-memory, persistent event loop)")
    return _instance


def get_stored_entity_types():
    return _entity_types


def get_stored_edge_types():
    return _edge_types


def get_stored_edge_type_map():
    return _edge_type_map


def store_ontology(entity_types, edge_types, edge_type_map):
    global _entity_types, _edge_types, _edge_type_map
    _entity_types = entity_types
    _edge_types = edge_types
    _edge_type_map = edge_type_map


def reset():
    """Reset singleton for next job."""
    global _instance, _entity_types, _edge_types, _edge_type_map, _loop, _thread
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(_loop.stop)
    _instance = None
    _entity_types = None
    _edge_types = None
    _edge_type_map = None
    _loop = None
    _thread = None
