"""
QueryAI — PostgreSQL connection management.
Two engines:
  • app_engine   → queryai_meta   (app metadata: history, conversations)
  • biz_engine   → queryai_demo   (read-only analytics database)
"""
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.core.logging import get_logger
from app.models.base import Base

log = get_logger(__name__)

app_connect_args = {}
if "postgresql" in settings.app_database_url:
    app_connect_args = {"connect_timeout": 10, "options": "-c statement_timeout=5000"}

biz_connect_args = {}
if "postgresql" in settings.business_database_url:
    biz_connect_args = {
        "connect_timeout": 10,
        "options": f"-c statement_timeout={settings.sql_query_timeout * 1000} -c default_transaction_read_only=on",
    }

# ── App metadata engine ────────────────────────────────────────────────────────
app_engine = create_engine(
    settings.app_database_url,
    pool_pre_ping=True,
    connect_args=app_connect_args,
)

# ── Business / analytics engine ──────────────────────────────────────────────
biz_engine = create_engine(
    settings.business_database_url,
    pool_pre_ping=True,
    connect_args=biz_connect_args,
)

AppSessionLocal = sessionmaker(bind=app_engine, autocommit=False, autoflush=False)
BizSessionLocal = sessionmaker(bind=biz_engine, autocommit=False, autoflush=False)


def init_app_db() -> None:
    """Create all app-metadata tables (idempotent)."""
    import os
    os.makedirs("storage", exist_ok=True)
    try:
        Base.metadata.create_all(bind=app_engine)
        log.info("App metadata tables initialized")
    except Exception as exc:
        log.error("Failed to initialize app DB tables", error=str(exc))
        raise


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields an app-metadata Session."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_app_db() -> dict:
    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "database": "queryai_meta"}
    except Exception as exc:
        return {"status": "disconnected", "error": str(exc)}


def check_biz_db() -> dict:
    try:
        with biz_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "database": "queryai_demo"}
    except Exception as exc:
        return {"status": "disconnected", "error": str(exc)}
