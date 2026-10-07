"""
QueryAI — Database Schema Inspector.
Uses SQLAlchemy inspect for portable metadata extraction (PostgreSQL, MySQL, SQLite).
Returns structured dicts used by the RAG indexer and the SQL generation prompt.
"""
from typing import Any
from sqlalchemy import inspect

from app.database.connection import biz_engine
from app.core.logging import get_logger

log = get_logger(__name__)


def get_full_schema() -> dict[str, Any]:
    """
    Return complete schema metadata for the business database.
    Database-agnostic using SQLAlchemy inspect.
    """
    tables: dict[str, Any] = {}
    try:
        inspector = inspect(biz_engine)
        table_names = inspector.get_table_names()

        for tname in table_names:
            if tname.startswith("pg_") or tname.startswith("app_"):
                continue

            # Columns
            cols = []
            try:
                for c in inspector.get_columns(tname):
                    cols.append({
                        "name": c["name"],
                        "type": str(c["type"]),
                        "nullable": c.get("nullable", True),
                        "default": str(c.get("default")) if c.get("default") is not None else None,
                        "comment": c.get("comment"),
                    })
            except Exception as e:
                log.warning(f"Could not inspect columns for {tname}: {e}")

            # Primary keys
            pks = []
            try:
                pk_info = inspector.get_pk_constraint(tname)
                pks = pk_info.get("constrained_columns", []) if pk_info else []
            except Exception:
                pass

            # Foreign keys
            fks = []
            try:
                fk_list = inspector.get_foreign_keys(tname)
                for fk in fk_list:
                    constrained = fk.get("constrained_columns", [])
                    referred = fk.get("referred_columns", [])
                    if constrained and referred:
                        fks.append({
                            "column": constrained[0],
                            "references_table": fk.get("referred_table", ""),
                            "references_column": referred[0],
                        })
            except Exception:
                pass

            tables[tname] = {
                "columns": cols,
                "primary_keys": pks,
                "foreign_keys": fks,
                "row_estimate": None,
                "description": None,
            }

    except Exception as exc:
        log.error("Failed to inspect schema", error=str(exc))

    return {"tables": tables, "schema": "public"}


def get_table_schema(table_name: str) -> dict[str, Any]:
    """Return schema metadata for a single table."""
    full = get_full_schema()
    tables = full["tables"]
    if table_name not in tables:
        raise KeyError(f"Table '{table_name}' not found in schema")
    return {"table": table_name, **tables[table_name]}


def schema_to_ddl(schema_data: dict[str, Any]) -> str:
    """
    Convert schema metadata to a compact DDL-like string for LLM prompts.
    Only includes selected tables/columns to keep token usage low.
    """
    lines = []
    for tname, tmeta in schema_data.get("tables", {}).items():
        col_defs = []
        pk_cols = set(tmeta.get("primary_keys", []))
        fk_map = {fk["column"]: fk for fk in tmeta.get("foreign_keys", [])}

        for col in tmeta.get("columns", []):
            cname = col["name"]
            ctype = str(col["type"]).upper()
            flags = []
            if cname in pk_cols:
                flags.append("PK")
            if cname in fk_map:
                fk = fk_map[cname]
                flags.append(f"FK→{fk['references_table']}.{fk['references_column']}")
            if not col["nullable"]:
                flags.append("NOT NULL")
            suffix = f"  -- {', '.join(flags)}" if flags else ""
            col_defs.append(f"  {cname} {ctype}{suffix}")

        desc = f"  -- {tmeta.get('description', '')}" if tmeta.get("description") else ""
        lines.append(f"TABLE {tname}{desc} (")
        lines.extend(col_defs)
        lines.append(")\n")

    return "\n".join(lines)

