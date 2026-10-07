"""
QueryAI — RAG-based schema retrieval using ChromaDB + nomic-embed-text.

Indexes schema metadata (table + column descriptions) as vector embeddings.
At query time, retrieves the most relevant tables/columns for a given question
so we only inject relevant schema into the LLM prompt.
"""
import json
from typing import Any
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import get_logger
from app.database.schema_inspector import get_full_schema, schema_to_ddl
from app.ai.hybrid_retriever import retrieve_tables_hybrid

log = get_logger(__name__)

_EMBED_MODEL = None


def _get_embed_fn():
    """Lazy-load the Ollama embedding function."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
        _EMBED_MODEL = OllamaEmbeddingFunction(
            url=f"{settings.ollama_base_url}/api/embeddings",
            model_name=settings.ollama_embed_model,
        )
    return _EMBED_MODEL


@lru_cache(maxsize=1)
def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _get_collection():
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chromadb_collection,
        embedding_function=_get_embed_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def index_schema(force: bool = False) -> int:
    """
    Index all schema metadata into ChromaDB.
    Each document = one table's full description (columns, types, PKs, FKs).
    Returns the number of documents indexed.
    """
    collection = _get_collection()

    # Skip if already indexed (and not forced)
    if not force and collection.count() > 0:
        log.info("Schema already indexed", count=collection.count())
        return collection.count()

    schema_data = get_full_schema()
    tables = schema_data["tables"]

    documents, metadatas, ids = [], [], []

    for table_name, tmeta in tables.items():
        # Build a rich text document for this table
        col_lines = []
        for col in tmeta.get("columns", []):
            col_lines.append(
                f"  - {col['name']} ({col['type']})"
                + (f": {col['comment']}" if col.get("comment") else "")
            )

        fk_lines = [
            f"  - {fk['column']} references {fk['references_table']}.{fk['references_column']}"
            for fk in tmeta.get("foreign_keys", [])
        ]

        doc_text = f"""Table: {table_name}
Description: {tmeta.get('description', 'No description available')}
Columns:
{chr(10).join(col_lines)}
Primary Keys: {', '.join(tmeta.get('primary_keys', []))}
Foreign Keys:
{chr(10).join(fk_lines) if fk_lines else '  None'}
Approximate row count: {tmeta.get('row_estimate', 'unknown')}
"""
        documents.append(doc_text)
        metadatas.append({
            "table_name": table_name,
            "column_names": json.dumps([c["name"] for c in tmeta.get("columns", [])]),
            "has_foreign_keys": bool(tmeta.get("foreign_keys")),
        })
        ids.append(f"table_{table_name}")

    if documents:
        # Upsert (delete then add to ensure freshness)
        try:
            existing_ids = [f"table_{t}" for t in tables]
            collection.delete(ids=existing_ids)
        except Exception:
            pass

        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        log.info("Schema indexed into ChromaDB", tables=len(documents))

    return len(documents)


def retrieve_relevant_tables(question: str, top_k: int = 5) -> list[str]:
    """
    Retrieve the most relevant table names for a given question.
    Returns a list of table names sorted by relevance.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            log.warning("Schema not indexed, indexing now...")
            index_schema()

        results = collection.query(
            query_texts=[question],
            n_results=min(15, collection.count()), # Fetch more for hybrid reranking
            include=["metadatas", "distances"],
        )

        vector_results = []
        if results and results.get("metadatas") and results.get("distances"):
            for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
                vector_results.append((meta["table_name"], dist))

        # Perform Hybrid Reranking
        full_schema = get_full_schema()
        table_names = retrieve_tables_hybrid(question, full_schema, vector_results, top_k=top_k)

        log.debug("Retrieved relevant tables (hybrid)", question=question[:50], tables=table_names)
        return table_names

    except Exception as exc:
        log.warning("RAG retrieval failed, falling back to full schema", error=str(exc))
        # Fallback: return all tables
        schema_data = get_full_schema()
        return list(schema_data["tables"].keys())


def get_relevant_schema_ddl(question: str, top_k: int = 6) -> tuple[str, list[str]]:
    """
    Returns (ddl_string, relevant_table_names) for injection into LLM prompt.
    """
    relevant_tables = retrieve_relevant_tables(question, top_k=top_k)
    full_schema = get_full_schema()

    # Filter to only relevant tables
    filtered = {"tables": {t: full_schema["tables"][t]
                           for t in relevant_tables if t in full_schema["tables"]}}

    # Also include tables that are referenced by FKs of relevant tables
    additional = set()
    for tname in relevant_tables:
        tmeta = full_schema["tables"].get(tname, {})
        for fk in tmeta.get("foreign_keys", []):
            ref_table = fk["references_table"]
            if ref_table not in filtered["tables"]:
                additional.add(ref_table)

    for tname in additional:
        if tname in full_schema["tables"]:
            filtered["tables"][tname] = full_schema["tables"][tname]

    ddl = schema_to_ddl(filtered)
    all_tables = list(filtered["tables"].keys())
    return ddl, all_tables
