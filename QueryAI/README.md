# QueryAI — AI-Powered Text-to-SQL Analytics Assistant

**QueryAI** is a production-ready, full-stack AI analytics application that allows business and technical users to query relational databases using natural language. It features schema-aware vector RAG, AST-based security validation, automatic SQL correction, and automated generation of charts and executive insights.

---

## 🌟 Key Features

- **Natural Language to SQL**: Converts complex business questions into high-performance, accurate SQL using local LLMs (Qwen 2.5 / Llama 3.2 via Ollama).
- **Schema-Aware Vector RAG**: Pre-indexes database tables and column definitions in ChromaDB using dense vector embeddings (`nomic-embed-text`), retrieving only relevant tables to minimize token usage and hallucination.
- **Multi-Layer SQL Security Validation**:
  - Keyword blocklist preventing data modifications (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc.).
  - AST-level syntax and statement validation via `sqlglot`.
  - Dangerous pattern and stacked query detection.
  - Join complexity limits to protect system resources.
- **Self-Healing Auto-Correction Loop**: Catches syntax or execution errors and invokes the LLM with error feedback and schema hints to fix queries automatically (up to configurable retry limits).
- **Interactive Visualizations**: Dynamically recommends the optimal Recharts visualization (Bar, Line, Pie, KPI Card, or Table).
- **Executive Summaries & Insights**: Automatically produces 2-4 sentence narrative insights explaining business trends found in query results.
- **Query Explanation**: Translates SQL statements into beginner-friendly explanations.
- **Audit History & Monitoring**: Stores full query execution metrics, query performance, and user conversations.

---

## 🏗️ Architecture

```
User Question
    │
    ▼
Schema RAG (ChromaDB + nomic-embed-text)
    │
    ▼
LLM Generation (Ollama / Qwen 2.5)
    │
    ▼
Multi-Layer Validator (sqlglot AST + Security Guard)
    │
    ├── [Error] ──► Auto-Correction Loop (Up to 2 Retries)
    ▼
Safe SQL Execution (Read-only DB + Statement Timeout + Row Limit)
    │
    ├── Recharts Visualization Recommendation (Bar / Line / Pie / KPI)
    └── Automated Business Insight Generation
```

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) running locally with models:
  ```bash
  ollama pull qwen2.5:7b
  ollama pull nomic-embed-text
  ```
- PostgreSQL or MySQL database
- ChromaDB

### 2. Environment Configuration
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

Key configuration parameters:
```ini
APP_DATABASE_URL=sqlite:///./storage/queryai_meta.db
BUSINESS_DATABASE_URL=mysql+pymysql://root:rootpassword123@localhost:3306/ai_assistant_demo
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
```

### 3. Run Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Interactive API documentation will be available at:
`http://localhost:8080/api/docs`

### 4. Run Test Suite
```bash
PYTHONPATH=QueryAI/backend pytest QueryAI/tests -v
```

All 19 unit and integration tests run in under 1 second.

---

## 📡 API Reference

### `POST /api/v1/query`
Run full natural language to SQL pipeline with visualization and insights.
```json
{
  "question": "What are the top 3 customers by lifetime value?",
  "conversation_id": null,
  "max_rows": 100
}
```

Response:
```json
{
  "query_id": "893db6ee-7c64-4bfd-a1c6-2244248a3ba5",
  "status": "success",
  "generated_sql": "SELECT first_name, last_name, email, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 3;",
  "result": {
    "columns": ["first_name", "last_name", "email", "lifetime_value"],
    "rows": [
      ["Robert", "Johnson", "r.johnson@techcorp.io", 196711.0],
      ["Amanda", "Williams", "a.williams@globalfin.com", 98992.8],
      ["Grace", "Kim", "g.kim@koreacorp.kr", 98498.2]
    ],
    "row_count": 3,
    "execution_time_ms": 2.03
  },
  "visualization": {
    "type": "bar",
    "x_column": "first_name",
    "y_column": "lifetime_value",
    "reason": "Comparisons between top 3 customers"
  },
  "insight": "The top 3 customers by lifetime value are Robert Johnson with $196,711.00, followed closely by Amanda Williams at $98,992.80, and Grace Kim at $98,498.20."
}
```

### `POST /api/v1/query/validate`
Dry-run security validation for a SQL query without executing it.

### `POST /api/v1/query/explain`
Returns beginner-friendly plain language explanation of SQL logic.

### `GET /api/v1/schema`
Inspects complete schema metadata (tables, columns, primary and foreign keys).

### `GET /api/v1/history`
Retrieves paginated audit log of queries, execution times, and visualization types.

---

## 🧪 Testing

The codebase includes comprehensive unit and integration test coverage:
- **Security Tests**: Verifies rejection of `DROP`, `DELETE`, `UPDATE`, stacked queries, time-based injection attacks, and complex joins.
- **RAG & DDL Tests**: Validates metadata extraction and compact prompt formatting.
- **Insights Tests**: Heuristics for line charts, bar charts, KPI cards, and pie charts.
- **API Tests**: Validates `/health`, `/api/v1/system/status`, `/api/v1/schema`, `/api/v1/history`, and query validation.
