"""
QueryAI — Hybrid Schema Retrieval.

Combines:
  1. Semantic Vector Search (ChromaDB)
  2. Keyword / Entity Matching (Regex)
  3. Foreign Key Graph Walk (Relationships)

Calculates a composite relevance score for each table and returns the top K.
"""
import re
from collections import defaultdict
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)


def retrieve_tables_hybrid(
    question: str,
    full_schema: dict[str, Any],
    vector_retrieved_tables: list[tuple[str, float]],
    top_k: int = 6,
) -> list[str]:
    """
    Perform hybrid scoring to find the most relevant tables.
    
    Args:
        question: The user's query
        full_schema: Complete schema metadata from schema_inspector
        vector_retrieved_tables: List of (table_name, distance_score) from ChromaDB
        top_k: Number of tables to return
    """
    q_lower = question.lower()
    scores: dict[str, float] = defaultdict(float)
    
    tables = full_schema.get("tables", {})
    if not tables:
        return []

    # 1. Vector Scores (convert distance to similarity)
    for tname, distance in vector_retrieved_tables:
        if tname in tables:
            # Distance is typically 0 to 2 (cosine). Lower is better.
            sim = max(0, 1.0 - (distance / 2.0))
            scores[tname] += sim * 40.0  # Max 40 points from vector

    # 2. Keyword / Entity Match (Columns and Table Names)
    # Extract potential words from the question
    words = set(re.findall(r"\b\w{3,}\b", q_lower))
    
    for tname, tmeta in tables.items():
        # Exact table name match
        if tname.lower() in q_lower:
            scores[tname] += 30.0
            
        # Partial table name match
        for word in words:
            if word in tname.lower():
                scores[tname] += 10.0
                
        # Column matches
        for col in tmeta.get("columns", []):
            cname = col["name"].lower()
            if cname in q_lower:
                scores[tname] += 15.0
            else:
                for word in words:
                    if word in cname:
                        scores[tname] += 5.0

    # 3. Foreign Key Graph Boost
    # If a table has a high score, tables connected to it via FKs get a boost
    fk_boosts = defaultdict(float)
    for tname, score in scores.items():
        if score > 20:  # Only boost neighbors of reasonably relevant tables
            tmeta = tables.get(tname, {})
            # Outgoing FKs
            for fk in tmeta.get("foreign_keys", []):
                ref_table = fk["references_table"]
                fk_boosts[ref_table] += score * 0.3  # 30% of parent's score
                
    for tname, boost in fk_boosts.items():
        scores[tname] += boost
        
    # Also find incoming FKs
    for tname, tmeta in tables.items():
        for fk in tmeta.get("foreign_keys", []):
            ref_table = fk["references_table"]
            if ref_table in scores and scores[ref_table] > 20:
                scores[tname] += scores[ref_table] * 0.3

    # Sort by score descending
    sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    log.debug(
        "Hybrid retrieval scores", 
        top=[f"{t}: {s:.1f}" for t, s in sorted_tables[:top_k]]
    )
    
    return [t for t, s in sorted_tables[:top_k]]
