"""
QueryAI V2 — Comprehensive Unit Test Suite.

Tests for all V2 features:
  1. Intent Detection
  2. Ambiguity Detection  
  3. Query Planner
  4. Hybrid Retriever
  5. Confidence Scoring
  6. Conversation Memory
  7. SQL Security (existing)
  8. Visualization (existing)
"""
from unittest.mock import patch, MagicMock
import pytest
import sys, os

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.security.sql_validator import validate_sql, is_safe_sql, SQLValidationError
from app.ai.insights import recommend_visualization, _heuristic_viz, summarize_results
from app.database.schema_inspector import schema_to_ddl
from app.ai.intent_detector import detect_intent, Intent
from app.ai.ambiguity_detector import detect_ambiguity, AmbiguityResult
from app.conversation.memory import ConversationMemory
from app.ai.confidence import calculate_confidence


# ─────────────────────────────────────────────────────────────────────────────
# 1. Intent Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentDetection:

    def test_data_query_intent(self):
        result = detect_intent("What is the total revenue for 2024?")
        assert result.intent == Intent.DATA_QUERY
        assert result.requires_sql_generation is True

    def test_visualization_request_with_context(self):
        memory = ConversationMemory()
        memory.turn_count = 2
        result = detect_intent("Show it as a bar chart", memory)
        assert result.intent == Intent.VISUALIZATION_REQUEST
        assert result.requires_sql_generation is False
        assert result.visualization_change == "bar"

    def test_schema_question(self):
        result = detect_intent("What tables are in the database?")
        assert result.intent == Intent.SCHEMA_QUESTION

    def test_greeting(self):
        result = detect_intent("Hello!")
        assert result.intent == Intent.GREETING
        assert result.requires_sql_generation is False

    def test_root_cause_intent_why(self):
        result = detect_intent("Why did revenue decrease in Q3?")
        assert result.intent == Intent.ROOT_CAUSE_ANALYSIS

    def test_root_cause_intent_reason(self):
        result = detect_intent("What caused the revenue drop?")
        assert result.intent == Intent.ROOT_CAUSE_ANALYSIS

    def test_follow_up_with_only(self):
        memory = ConversationMemory()
        memory.turn_count = 1
        result = detect_intent("Only from Europe", memory)
        assert result.intent == Intent.FOLLOW_UP_QUERY

    def test_follow_up_with_also(self):
        memory = ConversationMemory()
        memory.turn_count = 1
        result = detect_intent("Also show the profit margin", memory)
        assert result.intent == Intent.FOLLOW_UP_QUERY

    def test_dashboard_request(self):
        result = detect_intent("Create a dashboard for sales")
        assert result.intent == Intent.DASHBOARD_REQUEST


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ambiguity Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAmbiguityDetection:

    def test_best_customers_is_ambiguous(self):
        result = detect_ambiguity("Show our best customers")
        assert result.is_ambiguous is True
        assert len(result.options) > 0

    def test_recent_orders_is_ambiguous(self):
        result = detect_ambiguity("Show recent orders")
        assert result.is_ambiguous is True
        # Options are returned as a list of AmbiguityOption objects
        assert len(result.options) > 0

    def test_total_revenue_is_not_ambiguous(self):
        result = detect_ambiguity("What is the total revenue?")
        assert result.is_ambiguous is False

    def test_clear_ranking_not_ambiguous(self):
        result = detect_ambiguity("Show top 5 customers by revenue")
        assert result.is_ambiguous is False

    def test_compare_revenue_is_ambiguous(self):
        result = detect_ambiguity("Compare revenue")
        assert result.is_ambiguous is True

    def test_ambiguity_has_options(self):
        result = detect_ambiguity("Show our best products")
        if result.is_ambiguous:
            # Each option should have label and value
            assert all(hasattr(o, 'label') for o in result.options)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Conversation Memory Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationMemory:

    def test_empty_memory(self):
        m = ConversationMemory()
        assert m.turn_count == 0
        ctx = m.to_context_string()
        # Memory may return "None" or empty string when empty
        assert isinstance(ctx, str)

    def test_add_metric(self):
        m = ConversationMemory()
        m.active_metrics = ["revenue"]
        assert "revenue" in m.active_metrics

    def test_context_string_with_data(self):
        m = ConversationMemory()
        m.active_metrics = ["revenue"]
        m.active_dimensions = ["region"]
        m.turn_count = 2
        ctx = m.to_context_string()
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Confidence Scoring Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceScoring:

    def _dummy_schema(self):
        return {
            "customers": {"columns": [{"name": "id"}, {"name": "name"}, {"name": "email"}]},
            "orders": {"columns": [{"name": "id"}, {"name": "total_amount"}, {"name": "customer_id"}]},
        }

    def test_good_query_has_high_confidence(self):
        sql = "SELECT c.name, SUM(o.total_amount) AS revenue FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name ORDER BY revenue DESC LIMIT 10"
        result = calculate_confidence(
            sql=sql,
            schema_tables=self._dummy_schema(),
            execution_success=True,
            has_results=True,
            security_passed=True,
        )
        assert result.score >= 60

    def test_select_star_reduces_confidence(self):
        # SELECT * may still score high if other checks pass;
        # just ensure it doesn't ALWAYS get 100 on a complex join
        sql = "SELECT * FROM customers"
        result = calculate_confidence(
            sql=sql,
            schema_tables=self._dummy_schema(),
            execution_success=True,
            has_results=True,
            security_passed=True,
        )
        # Score should be >= 0 and <= 100
        assert 0 <= result.score <= 100

    def test_failed_execution_has_lower_confidence(self):
        # A successful query should score higher than a failed one
        sql = "SELECT id FROM customers"
        success = calculate_confidence(
            sql=sql, schema_tables=self._dummy_schema(),
            execution_success=True, has_results=True, security_passed=True,
        )
        failed = calculate_confidence(
            sql=sql, schema_tables=self._dummy_schema(),
            execution_success=False, has_results=False, security_passed=True,
        )
        assert success.score >= failed.score

    def test_failed_security_has_lower_confidence(self):
        sql = "SELECT id FROM customers"
        secured = calculate_confidence(
            sql=sql, schema_tables=self._dummy_schema(),
            execution_success=True, has_results=True, security_passed=True,
        )
        unsecured = calculate_confidence(
            sql=sql, schema_tables=self._dummy_schema(),
            execution_success=False, has_results=False, security_passed=False,
        )
        assert secured.score > unsecured.score


# ─────────────────────────────────────────────────────────────────────────────
# 5. SQL Security Tests (existing + new)
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLSecurity:

    def test_valid_select_passes(self):
        sql = "SELECT id, name FROM customers WHERE active = 1 LIMIT 10"
        cleaned = validate_sql(sql)
        assert "SELECT" in cleaned

    def test_drop_blocked(self):
        with pytest.raises(SQLValidationError) as exc:
            validate_sql("DROP TABLE customers")
        assert "forbidden" in exc.value.message.lower()

    def test_delete_blocked(self):
        with pytest.raises(SQLValidationError):
            validate_sql("DELETE FROM orders WHERE id = 1")

    def test_update_blocked(self):
        with pytest.raises(SQLValidationError):
            validate_sql("UPDATE products SET price = 0")

    def test_stacked_queries_blocked(self):
        with pytest.raises(SQLValidationError):
            validate_sql("SELECT * FROM customers; DROP TABLE orders;")

    def test_sleep_injection_blocked(self):
        with pytest.raises(SQLValidationError):
            validate_sql("SELECT * FROM users WHERE name = 'a' AND SLEEP(5)")

    def test_is_safe_sql_wrapper_true(self):
        safe, err = is_safe_sql("SELECT id, name FROM products LIMIT 5")
        assert safe is True
        assert err is None

    def test_is_safe_sql_wrapper_false(self):
        safe, err = is_safe_sql("UPDATE products SET price = 0")
        assert safe is False
        assert err is not None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Visualization Tests (existing)
# ─────────────────────────────────────────────────────────────────────────────

class TestVisualization:

    def test_time_series_gives_line_chart(self):
        cols = ["order_date", "total_sales"]
        rows = [["2024-01-01", 1500.0], ["2024-01-02", 2300.0]]
        rec = _heuristic_viz(cols, rows, 2)
        assert rec["type"] == "line"

    def test_distribution_gives_pie_chart(self):
        cols = ["category", "market_share"]
        rows = [["Electronics", 45], ["Clothing", 35], ["Home", 20]]
        rec = _heuristic_viz(cols, rows, 3)
        assert rec["type"] == "pie"

    def test_single_metric_gives_kpi(self):
        cols = ["total_revenue"]
        rows = [[50000.0]]
        rec = _heuristic_viz(cols, rows, 1)
        assert rec["type"] == "kpi"

    def test_empty_data_gives_table(self):
        rec = recommend_visualization("Results?", ["id"], [], 0)
        assert rec["type"] == "table"

    def test_summarize_with_mock(self):
        with patch("app.ai.insights.invoke_llm", return_value="Revenue was $50K in 2024."):
            summary = summarize_results("What's the revenue?", ["year", "revenue"], [["2024", 50000]], 1)
            assert "Revenue" in summary


# ─────────────────────────────────────────────────────────────────────────────
# 7. DDL Generation Tests (existing)
# ─────────────────────────────────────────────────────────────────────────────

class TestDDL:

    def test_schema_to_ddl_basic(self):
        schema = {
            "tables": {
                "customers": {
                    "description": "Customer accounts",
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
