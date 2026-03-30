"""Graphiti + Kuzu singleton for MiroFish shadow modules."""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_instance = None
_entity_types = None
_edge_types = None
_edge_type_map = None


def _run(coro):
    """Run async coroutine from sync context."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


async def get_graphiti_instance():
    """Lazy singleton — creates Graphiti with Kuzu in-memory + vLLM + OpenAI embedder."""
    global _instance
    if _instance is not None:
        return _instance

    from graphiti_core import Graphiti
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    driver = KuzuDriver(db=":memory:")

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

    _instance = Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
    )
    logger.info("Graphiti + Kuzu initialized (in-memory)")
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
    global _instance, _entity_types, _edge_types, _edge_type_map
    _instance = None
    _entity_types = None
    _edge_types = None
    _edge_type_map = None
