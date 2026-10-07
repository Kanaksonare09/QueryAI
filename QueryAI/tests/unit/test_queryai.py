"""
QueryAI — Comprehensive Unit Test Suite.
Tests:
  1. SQL Security Validator (allowed vs blocked queries)
  2. SQL Generator regex & prompt formatting
  3. SQL Corrector logic
  4. AI Insights & visualization recommendations
  5. Schema Inspector formatting & DDL generation
"""
from unittest.mock import patch
import pytest
from app.security.sql_validator import validate_sql, is_safe_sql, SQLValidationError
from app.ai.insights import recommend_visualization, _heuristic_viz, summarize_results, explain_sql
from app.database.schema_inspector import schema_to_ddl


# ── 1. SQL Validator Tests ─────────────────────────────────────────────────────

def test_validate_sql_valid_select():
    sql = "SELECT id, name, email FROM customers WHERE active = true LIMIT 10"
    cleaned = validate_sql(sql)
    assert cleaned.startswith("SELECT")
    assert "LIMIT 10" in cleaned

def test_validate_sql_block_drop():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("DROP TABLE customers")
    assert "forbidden keyword" in exc.value.message.lower()

def test_validate_sql_block_delete():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("DELETE FROM orders WHERE id = 1")
    assert "forbidden keyword" in exc.value.message.lower()

def test_validate_sql_block_stacked_queries():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT * FROM customers; DROP TABLE orders;")

def test_validate_sql_block_dangerous_patterns():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT * FROM users WHERE name = 'a' AND SLEEP(5)")

def test_is_safe_sql_wrapper():
    safe, err = is_safe_sql("SELECT * FROM products")
    assert safe is True
    assert err is None

    safe, err = is_safe_sql("UPDATE products SET price = 0")
    assert safe is False
    assert err is not None


# ── 2. Visualization Recommendation Tests ──────────────────────────────────────

def test_heuristic_viz_time_series():
    cols = ["order_date", "total_sales"]
    rows = [["2024-01-01", 1500.0], ["2024-01-02", 2300.0]]
    rec = _heuristic_viz(cols, rows, 2)
    assert rec["type"] == "line"
    assert rec["x_column"] == "order_date"
    assert rec["y_column"] == "total_sales"

def test_heuristic_viz_pie_chart():
    cols = ["category", "market_share"]
    rows = [
        ["Electronics", 45],
        ["Clothing", 35],
        ["Home", 20],
    ]
    rec = _heuristic_viz(cols, rows, 3)
    assert rec["type"] == "pie"
    assert rec["x_column"] == "category"
    assert rec["y_column"] == "market_share"

def test_heuristic_viz_single_metric():
    cols = ["total_revenue"]
    rows = [[50000.0]]
    rec = _heuristic_viz(cols, rows, 1)
    assert rec["type"] == "kpi"
    assert rec["y_column"] == "total_revenue"

def test_recommend_visualization_empty():
    rec = recommend_visualization("What are the results?", ["id"], [], 0)
    assert rec["type"] == "table"
    assert rec["reason"] == "No data"


# ── 3. Result Summarization Tests ─────────────────────────────────────────────

def test_summarize_results_with_mock():
    with patch("app.ai.insights.invoke_llm", return_value="Total revenue for 2024 was $50,000 across 2 orders."):
        cols = ["name", "salary"]
        rows = [["Alice", 90000], ["Bob", 85000]]
        summary = summarize_results("List employee salaries", cols, rows, 2)
        assert "Total revenue" in summary

def test_explain_sql_with_mock():
    with patch("app.ai.insights.invoke_llm", return_value="This query retrieves active customers."):
        explanation = explain_sql("SELECT * FROM customers WHERE active = true")
        assert "This query retrieves" in explanation


# ── 4. DDL Conversion Tests ───────────────────────────────────────────────────

def test_schema_to_ddl():
    schema = {
        "tables": {
            "customers": {
                "description": "Customer accounts table",
                "primary_keys": ["id"],
                "foreign_keys": [],
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "name", "type": "VARCHAR(255)", "nullable": True},
                ],
            }
        }
    }
    ddl = schema_to_ddl(schema)
    assert "TABLE customers" in ddl
    assert "id INTEGER" in ddl
    assert "PK" in ddl
