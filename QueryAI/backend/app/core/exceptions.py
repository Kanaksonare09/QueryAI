"""
QueryAI Backend — Custom Exception Hierarchy
"""
from fastapi import HTTPException, status


class QueryAIException(Exception):
    """Base exception for all QueryAI errors."""
    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class SQLValidationError(QueryAIException):
    """Raised when generated SQL fails security or syntax validation."""
    pass


class SQLExecutionError(QueryAIException):
    """Raised when SQL execution fails."""
    def __init__(self, message: str, sql: str, original_error: str):
        super().__init__(message, original_error)
        self.sql = sql
        self.original_error = original_error


class SQLCorrectionFailedError(QueryAIException):
    """Raised when auto-correction exhausts all retries."""
    pass


class LLMError(QueryAIException):
    """Raised when LLM is unavailable or returns bad output."""
    pass


class SchemaNotFoundError(QueryAIException):
    """Raised when schema metadata is not found or stale."""
    pass


class DatabaseConnectionError(QueryAIException):
    """Raised when database connection fails."""
    pass


class RateLimitError(QueryAIException):
    """Raised when user exceeds rate limit."""
    pass


# HTTP exception helpers
def http_not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def http_bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def http_internal(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def http_unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
