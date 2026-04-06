"""
Knowledge graph operations: build, refine, deduplicate, and infer edges.
"""
from __future__ import annotations

import json
import os
import time


def _extract_enrichment_hints(seed_text: str) -> str | None:
    """Extract entity hints from the enrichment section of the seed text."""
    marker = "--- Background Research ---"
    if marker not in seed_text:
        return None
    research = seed_text.split(marker, 1)[1].strip()
    if not research:
        return None
    return (
        "The following background research was gathered from web and social media search. "
        "Use it to identify key entities, their roles, and relationships that should be "
        "represented in the ontology:\n\n" + research[:3000]
    )


def build_graph(seed_text: str, goal: str, storage) -> tuple[str, str]:
    """
    Steps 1-2: Generate ontology, build Neo4j graph via MiroShark's storage.
    Returns (project_id, graph_id).

    ``storage`` is a Neo4jStorage instance (created externally so the caller
    can pass it to later pipeline steps).
    """
    from app.services.ontology_generator import OntologyGenerator
    from app.services.text_processor import TextProcessor

    # Extract enrichment hints for ontology
    enrichment_hints = _extract_enrichment_hints(seed_text)
    if enrichment_hints:
        print("[run_job] Using enrichment research as ontology context", flush=True)

    print("[run_job] Step 1: Generating ontology...", flush=True)
    ontology_gen = OntologyGenerator()
    ontology = ontology_gen.generate(
        document_texts=[seed_text],
        simulation_requirement=goal,
        additional_context=enrichment_hints,
    )

    print("[run_job] Step 2: Building Neo4j knowledge graph...", flush=True)
    graph_id = storage.create_graph(name=f"SimSwarm-{int(time.time())}")
    storage.set_ontology(graph_id, ontology)

    # Split text, ingest in batches
    chunks = TextProcessor.split_text(seed_text, chunk_size=500, overlap=50)
    storage.add_text_batch(graph_id, chunks, batch_size=3)

    # Post-ingestion: deduplicate entities + infer missing relationships
    try:
        _refine_graph(graph_id, goal, storage)
    except Exception as exc:
        print(f"[run_job] WARNING: graph refinement failed: {exc}", flush=True)

    info = storage.get_graph_info(graph_id)
    print(f"[run_job] Graph ready: graph_id={graph_id}, nodes={info.get('node_count', 0)}, edges={info.get('edge_count', 0)}", flush=True)

    project_id = graph_id
    return project_id, graph_id


# ---------------------------------------------------------------------------
# Post-ingestion graph refinement (dedup + relationship inference)
# ---------------------------------------------------------------------------

def _refine_graph(graph_id: str, goal: str, storage) -> None:
    """Deduplicate entities and infer missing relationships via on-pod vLLM."""
    from app.utils.llm_client import LLMClient

    llm = LLMClient()
    nodes = storage.get_all_nodes(graph_id)
    if not nodes:
        return

    entity_names = [n.get("name", "") for n in nodes if n.get("name")]
    entity_info = [
        {"name": n.get("name", ""), "type": next((l for l in n.get("labels", []) if l not in ("Entity", "Node")), "Entity")}
        for n in nodes if n.get("name")
    ]

    # --- Step 1: Deduplicate entities ---
    dedup_prompt = (
        "Given these entity names extracted from a document, identify any groups "
        "that refer to the SAME real-world entity (abbreviations, partial names, "
        "alternate spellings).\n\n"
        f"Entity names: {json.dumps(entity_names)}\n\n"
        "Return a JSON array of groups. Each group is an array of names that "
        "should be merged. Only include groups with 2+ names. "
        "If no duplicates exist, return an empty array [].\n\n"
        "Example: [[\"Amnesty International\", \"Amnesty\"], [\"EU\", \"European Union\"]]"
    )

    try:
        groups = llm.chat_json(
            messages=[{"role": "user", "content": dedup_prompt}],
            temperature=0.1,
        )
        if not isinstance(groups, list):
            groups = groups.get("groups", []) if isinstance(groups, dict) else []

        merged_count = 0
        for group in groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            # Keep the longest name as canonical
            canonical = max(group, key=len)
            aliases = [n for n in group if n != canonical]
            for alias in aliases:
                try:
                    _merge_entities_in_neo4j(graph_id, alias, canonical)
                    merged_count += 1
                except Exception as exc:
                    print(f"[run_job] WARNING: merge failed {alias} → {canonical}: {exc}", flush=True)

        if merged_count:
            print(f"[run_job] Dedup: merged {merged_count} duplicate entities", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: entity dedup failed: {exc}", flush=True)

    # --- Step 2: Infer missing relationships ---
    # Refresh nodes after dedup
    nodes = storage.get_all_nodes(graph_id)
    edges = storage.get_all_edges(graph_id)

    entity_info = [
        {"name": n.get("name", ""), "type": next((l for l in n.get("labels", []) if l not in ("Entity", "Node")), "Entity")}
        for n in nodes if n.get("name")
    ]
    existing_pairs = set()
    for e in edges:
        src = e.get("source_node_name", "") or ""
        tgt = e.get("target_node_name", "") or ""
        if src and tgt:
            existing_pairs.add((src.lower(), tgt.lower()))
            existing_pairs.add((tgt.lower(), src.lower()))

    infer_prompt = (
        f"Simulation goal: {goal}\n\n"
        f"These entities were extracted from a document:\n{json.dumps(entity_info, indent=2)}\n\n"
        f"These relationships already exist between them (as source→target pairs):\n"
        f"{json.dumps(list(existing_pairs)[:50])}\n\n"
        "What additional relationships likely exist between these entities that "
        "were NOT explicitly stated in the text but are common knowledge? "
        "Focus on: collaboration, competition, regulation, membership, opposition.\n\n"
        "Return a JSON array of objects with: source, target, type (UPPER_SNAKE_CASE), "
        "fact (one sentence describing the relationship).\n"
        "Only include high-confidence relationships. Max 15.\n\n"
        "Example: [{\"source\": \"Access Now\", \"target\": \"EDRi\", "
        "\"type\": \"COLLABORATES_WITH\", \"fact\": \"Access Now is a member of EDRi\"}]"
    )

    try:
        inferred = llm.chat_json(
            messages=[{"role": "user", "content": infer_prompt}],
            temperature=0.2,
        )
        if not isinstance(inferred, list):
            inferred = inferred.get("relationships", []) if isinstance(inferred, dict) else []

        added_count = 0
        for rel in inferred:
            if not isinstance(rel, dict):
                continue
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            rtype = rel.get("type", "RELATED_TO")
            fact = rel.get("fact", "")
            if not src or not tgt:
                continue
            # Skip if already exists
            if (src.lower(), tgt.lower()) in existing_pairs:
                continue
            try:
                _add_inferred_edge(graph_id, src, tgt, rtype, fact)
                existing_pairs.add((src.lower(), tgt.lower()))
                added_count += 1
            except Exception as exc:
                print(f"[run_job] WARNING: add edge failed {src}→{tgt}: {exc}", flush=True)

        if added_count:
            print(f"[run_job] Inferred: added {added_count} missing relationships", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: relationship inference failed: {exc}", flush=True)


def _merge_entities_in_neo4j(graph_id: str, alias: str, canonical: str) -> None:
    """Merge alias entity into canonical entity in Neo4j."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    with driver.session() as session:
        # Move all edges from alias to canonical
        session.run(
            """
            MATCH (alias:Entity {graph_id: $gid, name_lower: $alias_lower})
            MATCH (canon:Entity {graph_id: $gid, name_lower: $canon_lower})
            WHERE alias <> canon
            OPTIONAL MATCH (alias)-[r]->()
            WITH alias, canon, collect(r) AS rels
            UNWIND rels AS r
            WITH alias, canon, r, endNode(r) AS target
            CREATE (canon)-[nr:RELATION]->(target)
            SET nr = properties(r)
            DELETE r
            """,
            gid=graph_id,
            alias_lower=alias.lower(),
            canon_lower=canonical.lower(),
        )
        # Move incoming edges
        session.run(
            """
            MATCH (alias:Entity {graph_id: $gid, name_lower: $alias_lower})
            MATCH (canon:Entity {graph_id: $gid, name_lower: $canon_lower})
            WHERE alias <> canon
            OPTIONAL MATCH ()-[r]->(alias)
            WITH alias, canon, collect(r) AS rels
            UNWIND rels AS r
            WITH alias, canon, r, startNode(r) AS source
            CREATE (source)-[nr:RELATION]->(canon)
            SET nr = properties(r)
            DELETE r
            """,
            gid=graph_id,
            alias_lower=alias.lower(),
            canon_lower=canonical.lower(),
        )
        # Delete alias node
        session.run(
            "MATCH (n:Entity {graph_id: $gid, name_lower: $alias_lower}) DETACH DELETE n",
            gid=graph_id,
            alias_lower=alias.lower(),
        )
    driver.close()


def _add_inferred_edge(graph_id: str, source: str, target: str, rel_type: str, fact: str) -> None:
    """Add an inferred relationship edge between two entities."""
    import uuid as _uuid
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    with driver.session() as session:
        session.run(
            """
            MATCH (s:Entity {graph_id: $gid, name_lower: $src_lower})
            MATCH (t:Entity {graph_id: $gid, name_lower: $tgt_lower})
            CREATE (s)-[r:RELATION {
                uuid: $uuid,
                graph_id: $gid,
                name: $rtype,
                fact: $fact,
                source: 'inferred',
                created_at: $now
            }]->(t)
            """,
            gid=graph_id,
            src_lower=source.lower(),
            tgt_lower=target.lower(),
            uuid=_uuid.uuid4().hex,
            rtype=rel_type,
            fact=fact,
            now=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    driver.close()
