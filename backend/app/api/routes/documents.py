"""
Document management API — upload, index, delete, search, collections.
"""
import os
import uuid
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Document, DocumentCollection, DocumentChunk, DocumentStatus
from app.schemas.schemas import DocumentOut, CollectionCreate, CollectionOut
from app.documents.extractor import DocumentExtractor
from app.documents.chunker import DocumentChunker
from app.rag.vector_store import VectorStore
from app.config import settings
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["Documents"])

STORAGE_PATH = Path(settings.storage_path) / "documents"
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


# ─── Documents ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[DocumentOut])
def list_documents(
    status: Optional[str] = None,
    collection_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    if collection_id:
        q = q.filter(Document.collection_id == collection_id)
    return q.order_by(Document.uploaded_at.desc()).all()


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload and asynchronously index a document."""
    # Validate extension
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {settings.allowed_extensions_list}",
        )

    # Validate size
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    # Save file
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}.{ext}"
    dest = STORAGE_PATH / safe_name
    dest.write_bytes(content)

    # Create DB record
    doc = Document(
        id=doc_id,
        filename=safe_name,
        original_filename=file.filename,
        file_type=ext,
        file_size=len(content),
        storage_path=str(dest),
        collection_id=collection_id,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Kick off background indexing
    background_tasks.add_task(_index_document, doc_id, str(dest), ext)

    return doc


async def _index_document(doc_id: str, file_path: str, file_type: str):
    """Background task: extract, chunk, embed, and index a document."""
    from app.database.session import AdminSession
    db = AdminSession()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        doc.status = DocumentStatus.processing
        db.commit()

        # Extract text
        extractor = DocumentExtractor()
        extracted = extractor.extract(file_path, file_type)

        # Chunk
        chunker = DocumentChunker()
        chunks = chunker.chunk_extracted(
            extracted=extracted,
            document_id=doc_id,
            filename=doc.original_filename,
            file_type=file_type,
        )

        # Save chunks to DB
        db_chunks = []
        for ch in chunks:
            db_chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=ch["chunk_index"],
                content=ch["content"],
                page_number=ch.get("page_number"),
                section=ch.get("section"),
            )
            db_chunks.append(db_chunk)
        db.add_all(db_chunks)

        # Embed and index in ChromaDB
        vs = VectorStore()
        chroma_ids = vs.add_chunks(chunks)

        # Update chunk Chroma IDs
        for db_chunk, cid in zip(db_chunks, chroma_ids):
            db_chunk.chroma_id = cid

        # Update document record
        doc.status = DocumentStatus.indexed
        doc.chunk_count = len(chunks)
        doc.page_count = extracted.get("page_count")
        doc.indexed_at = datetime.utcnow()
        db.commit()

        logger.info("Document indexed", doc_id=doc_id, chunks=len(chunks))
    except Exception as e:
        logger.error("Indexing failed", doc_id=doc_id, error=str(e))
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = DocumentStatus.failed
                doc.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.get("/search")
async def search_documents(
    q: str,
    top_k: int = 5,
    collection_id: Optional[str] = None,
):
    """Semantic search across all indexed documents via ChromaDB."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' must not be empty")
    try:
        vs = VectorStore()
        hits = vs.search(query=q, top_k=top_k)
        return {"query": q, "results": hits, "count": len(hits)}
    except Exception as e:
        logger.error("Document search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from vector store
    try:
        vs = VectorStore()
        vs.delete_document(doc_id)
    except Exception as e:
        logger.warning("Failed to delete from vector store", error=str(e))

    # Delete file
    try:
        Path(doc.storage_path).unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}


@router.post("/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete existing chunks
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    doc.status = DocumentStatus.pending
    doc.chunk_count = 0
    db.commit()

    # Remove from vector store
    try:
        vs = VectorStore()
        vs.delete_document(doc_id)
    except Exception:
        pass

    background_tasks.add_task(_index_document, doc_id, doc.storage_path, doc.file_type)
    return {"message": "Re-indexing started"}


# ─── Collections ──────────────────────────────────────────────────────────────

@router.get("/collections/all", response_model=List[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    collections = db.query(DocumentCollection).all()
    result = []
    for c in collections:
        doc_count = db.query(Document).filter(Document.collection_id == c.id).count()
        result.append(CollectionOut(
            id=c.id,
            name=c.name,
            description=c.description,
            color=c.color,
            document_count=doc_count,
            created_at=c.created_at,
        ))
    return result


@router.post("/collections", response_model=CollectionOut)
def create_collection(req: CollectionCreate, db: Session = Depends(get_db)):
    coll = DocumentCollection(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        color=req.color,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return CollectionOut(
        id=coll.id,
        name=coll.name,
        description=coll.description,
        color=coll.color,
        document_count=0,
        created_at=coll.created_at,
    )


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str, db: Session = Depends(get_db)):
    coll = db.query(DocumentCollection).filter(DocumentCollection.id == collection_id).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    # Unlink documents (don't delete them)
    db.query(Document).filter(Document.collection_id == collection_id).update({"collection_id": None})
    db.delete(coll)
    db.commit()
    return {"message": "Collection deleted"}
