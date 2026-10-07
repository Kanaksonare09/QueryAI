from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator
from app.config import settings
from app.models.models import Base
import structlog

logger = structlog.get_logger()

# Read-only engine (for user queries)
readonly_engine = create_engine(
    settings.mysql_readonly_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

# Admin engine (for schema inspection + app metadata)
admin_engine = create_engine(
    settings.mysql_admin_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

ReadonlySession = sessionmaker(bind=readonly_engine, autocommit=False, autoflush=False)
AdminSession = sessionmaker(bind=admin_engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for admin DB session."""
    db = AdminSession()
    try:
        yield db
    finally:
        db.close()


def get_readonly_db() -> Generator[Session, None, None]:
    """FastAPI dependency for read-only DB session."""
    db = ReadonlySession()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create application metadata tables."""
    try:
        Base.metadata.create_all(bind=admin_engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error("Failed to initialize database tables", error=str(e))
        raise


def check_mysql_connection() -> dict:
    """Check MySQL connectivity and return status."""
    try:
        with admin_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "host": settings.mysql_host, "database": settings.mysql_database}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}
