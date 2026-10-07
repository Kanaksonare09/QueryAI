"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.config import settings
from app.database.session import init_db
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as docs_router
from app.api.routes.system import router as system_router, db_router
from app.api.routes.conversations import router as conv_router
import structlog
import os

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    logger.info("Starting Offline AI Assistant backend...")
    # Create app metadata tables
    try:
        init_db()
    except Exception as e:
        logger.warning("DB init warning (may already exist)", error=str(e))

    # Pre-load embedding model (optional warmup)
    try:
        from app.rag.vector_store import get_embedding_model
        get_embedding_model()
        logger.info("Embedding model loaded")
    except Exception as e:
        logger.warning("Embedding model warmup failed", error=str(e))

    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Offline AI Data & Document Intelligence Assistant",
    description="Production-quality AI assistant with RAG, Text-to-SQL, MCP, and LangGraph.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routes — all under /api/v1 to match frontend axios baseURL
app.include_router(chat_router,   prefix="/api/v1")
app.include_router(docs_router,   prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(db_router,     prefix="/api/v1")
app.include_router(conv_router,   prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "Offline AI Assistant"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )
