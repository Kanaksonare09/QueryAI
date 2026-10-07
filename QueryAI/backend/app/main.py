"""
QueryAI Backend — FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import QueryAIException
from app.database.connection import init_app_db
from app.api.routes.query import router as query_router
from app.api.routes.system import schema_router, history_router, system_router
from app.api.routes.chat import chat_router, docs_router

setup_logging()
log = get_logger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("Starting QueryAI backend", env=settings.app_env)

    # Initialize app metadata tables
    try:
        init_app_db()
        log.info("App database tables ready")
    except Exception as exc:
        log.warning("App DB init warning", error=str(exc))

    # Index schema into ChromaDB on startup
    try:
        from app.ai.rag import index_schema
        count = index_schema()
        log.info("Schema indexed", tables=count)
    except Exception as exc:
        log.warning("Schema indexing failed on startup (will retry on first query)", error=str(exc))

    yield
    log.info("QueryAI backend shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QueryAI V2 — Conversational AI Database Analyst",
    description="""
**QueryAI V2** is a fully offline, conversational AI database analyst.

## Pipeline
1. Intent Detection → Ambiguity Check → Query Planning
2. Hybrid Schema RAG (vector + keyword + FK graph)
3. SQL Generation (Ollama/Qwen 2.5)
4. Multi-layer Security Validation (AST + keyword blocklist)
5. MySQL Execution + Auto-correction
6. Confidence Scoring + Query Optimization (EXPLAIN)
7. Visualization + Business Insight Generation

## Investigation Mode
For "why" questions, runs a multi-step root-cause investigation:
Baseline → Dimension Breakdowns → Driver Ranking → Evidence-backed Explanation

## Security
- Read-only MySQL user
- sqlglot AST validation
- Keyword + regex blocklist
- Query timeout & row limits
- Rate limiting
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(QueryAIException)
async def queryai_exception_handler(request: Request, exc: QueryAIException):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "extra": exc.detail},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(query_router,   prefix="/api/v1")
app.include_router(chat_router,    prefix="/api/v1")
app.include_router(docs_router,    prefix="/api/v1")
app.include_router(schema_router,  prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(system_router,  prefix="/api/v1")

# Alias /database/schema → /schema for SchemaExplorer UI
from fastapi import APIRouter as _APIRouter
_db_router = _APIRouter(prefix="/database", tags=["Database"])

@_db_router.get("/schema")
async def get_database_schema_alias():
    """Alias endpoint so frontend /database/schema returns full schema."""
    from app.services.schema_history_service import get_schema_overview
    return get_schema_overview()

app.include_router(_db_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": "QueryAI", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.is_development,
        log_level="debug" if settings.debug else "info",
    )
