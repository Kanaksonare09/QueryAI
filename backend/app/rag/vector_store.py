"""
ChromaDB vector store manager — handles embeddings, indexing, and retrieval.
Uses local Sentence Transformers model (all-MiniLM-L6-v2).
"""
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from app.config import settings
import structlog

logger = structlog.get_logger()

_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.HttpClient] = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model", model=settings.embedding_model)
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def get_chroma_client() -> chromadb.HttpClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
    return _chroma_client


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


class VectorStore:
    def __init__(self):
        self.model = get_embedding_model()
        self.collection = get_collection()

    def embed_text(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Add document chunks to ChromaDB.
        Each chunk: {chunk_index, content, page_number, section,
                     document_id, filename, file_type}
        Returns list of chroma IDs.
        """
        if not chunks:
            return []

        ids = [f"{c['document_id']}_{c['chunk_index']}" for c in chunks]
        texts = [c["content"] for c in chunks]
        embeddings = self.embed_batch(texts)
        metadatas = [
            {
                "document_id": c["document_id"],
                "filename": c["filename"],
                "file_type": c["file_type"],
                "page_number": str(c["page_number"]) if c["page_number"] else "",
                "section": c["section"] or "",
                "chunk_index": str(c["chunk_index"]),
            }
            for c in chunks
        ]

        # ChromaDB upsert (safe for re-indexing)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Indexed chunks", count=len(chunks))
        return ids

    def search(
        self,
        query: str,
        top_k: int = None,
        document_ids: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with optional metadata filtering.
        Returns ranked list of {content, metadata, score, distance}.
        """
        top_k = top_k or settings.top_k_retrieval
        query_embedding = self.embed_text(query)

        where_clause = None
        where_conditions = []
        if document_ids:
            if len(document_ids) == 1:
                where_conditions.append({"document_id": {"$eq": document_ids[0]}})
            else:
                where_conditions.append({"document_id": {"$in": document_ids}})
        if file_types:
            if len(file_types) == 1:
                where_conditions.append({"file_type": {"$eq": file_types[0]}})
            else:
                where_conditions.append({"file_type": {"$in": file_types}})

        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            where_clause = {"$and": where_conditions}

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause:
            kwargs["where"] = where_clause

        try:
            results = self.collection.query(**kwargs)
        except Exception as e:
            logger.error("ChromaDB query failed", error=str(e))
            return []

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "content": doc,
                "metadata": meta,
                "score": 1 - dist,  # cosine similarity
                "distance": dist,
            })

        return hits

    def delete_document(self, document_id: str) -> None:
        """Remove all chunks for a document from ChromaDB."""
        self.collection.delete(where={"document_id": {"$eq": document_id}})
        logger.info("Deleted document from vector store", document_id=document_id)

    def get_collection_stats(self) -> Dict[str, int]:
        count = self.collection.count()
        return {"total_chunks": count}


def format_citations(hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Format search hits as citation objects."""
    seen = set()
    citations = []
    for hit in hits:
        meta = hit["metadata"]
        key = f"{meta['document_id']}_{meta.get('page_number', '')}_{meta.get('section', '')}"
        if key not in seen:
            seen.add(key)
            citation = {
                "filename": meta["filename"],
                "file_type": meta["file_type"],
                "document_id": meta["document_id"],
                "score": round(hit["score"], 3),
            }
            if meta.get("page_number"):
                citation["page"] = meta["page_number"]
            if meta.get("section"):
                citation["section"] = meta["section"]
            citations.append(citation)
    return citations
