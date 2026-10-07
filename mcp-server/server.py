"""
MCP Server — exposes safe, domain-specific tools to the LangGraph agent.
Tools: query_database, search_documents, get_schema_info, calculate_metrics
"""
import os, json, re
from typing import Any
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# ── Attempt to use fastmcp; fall back to a minimal HTTP shim ──────────────
try:
    from fastmcp import FastMCP
    USE_FASTMCP = True
except ImportError:
    USE_FASTMCP = False

# ── DB config ─────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_READONLY_USER", "ai_readonly"),
    "password": os.getenv("MYSQL_READONLY_PASSWORD", "readonly_pass_123"),
    "database": os.getenv("MYSQL_DATABASE", "ai_assistant_demo"),
}

BLOCKED_KEYWORDS = {"drop","delete","truncate","insert","update","alter","create",
                    "grant","revoke","exec","execute","xp_","sp_","--","/*","*/",";--"}

def _is_safe_query(sql: str) -> bool:
    tokens = set(re.findall(r'\b\w+\b', sql.lower()))
    return not (tokens & BLOCKED_KEYWORDS)

def _run_sql(sql: str, limit: int = 100) -> dict[str, Any]:
    if not sql.strip().lower().startswith("select"):
        return {"error": "Only SELECT statements are allowed."}
    if not _is_safe_query(sql):
        return {"error": "Query contains forbidden keywords."}
    # inject limit
    if "limit" not in sql.lower():
        sql = sql.rstrip(";") + f" LIMIT {limit}"
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []
        cursor.close(); conn.close()
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e)}

def _get_schema() -> dict[str, Any]:
    sql = """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (DB_CONFIG["database"],))
        rows = cursor.fetchall()
        cursor.close(); conn.close()
        schema: dict = {}
        for r in rows:
            tbl = r["TABLE_NAME"]
            schema.setdefault(tbl, []).append({
                "column": r["COLUMN_NAME"],
                "type": r["DATA_TYPE"],
                "nullable": r["IS_NULLABLE"],
                "key": r["COLUMN_KEY"],
            })
        return {"tables": schema}
    except Exception as e:
        return {"error": str(e)}

def _search_documents(query: str, n_results: int = 5) -> dict[str, Any]:
    """Proxy to ChromaDB via the backend API."""
    try:
        import requests
        backend = os.getenv("BACKEND_URL", "http://backend:8080")
        r = requests.post(
            f"{backend}/api/v1/documents/search",
            json={"query": query, "n_results": n_results},
            timeout=15,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _calculate_metrics(metric: str, params: dict) -> dict[str, Any]:
    """Calculate common business metrics from DB data."""
    METRICS = {
        "revenue_growth": """
            SELECT
                YEAR(sale_date) as year,
                MONTH(sale_date) as month,
                SUM(total_amount) as revenue
            FROM sales
            GROUP BY YEAR(sale_date), MONTH(sale_date)
            ORDER BY year, month
        """,
        "top_products": """
            SELECT p.name, SUM(s.total_amount) as total_revenue,
                   COUNT(s.id) as transactions
            FROM sales s
            JOIN products p ON s.product_id = p.id
            GROUP BY p.id, p.name
            ORDER BY total_revenue DESC
            LIMIT 10
        """,
        "customer_segments": """
            SELECT customer_segment, COUNT(*) as count,
                   AVG(total_amount) as avg_order_value,
                   SUM(total_amount) as total_revenue
            FROM sales
            GROUP BY customer_segment
        """,
        "regional_performance": """
            SELECT region, SUM(total_amount) as revenue,
                   COUNT(*) as deals, AVG(total_amount) as avg_deal
            FROM sales
            GROUP BY region
            ORDER BY revenue DESC
        """,
    }
    sql = METRICS.get(metric)
    if not sql:
        return {"error": f"Unknown metric '{metric}'. Available: {list(METRICS.keys())}"}
    return _run_sql(sql.strip())


# ══════════════════════════════════════════════════════════════════════════
# FastMCP path
# ══════════════════════════════════════════════════════════════════════════
if USE_FASTMCP:
    mcp = FastMCP("AI Assistant Tools")

    @mcp.tool()
    def query_database(sql: str, limit: int = 100) -> str:
        """Execute a read-only SQL SELECT query against the business database."""
        result = _run_sql(sql, limit)
        return json.dumps(result, default=str)

    @mcp.tool()
    def get_schema_info() -> str:
        """Get the database schema including all tables and columns."""
        return json.dumps(_get_schema(), default=str)

    @mcp.tool()
    def search_documents(query: str, n_results: int = 5) -> str:
        """Semantically search the indexed document collection."""
        return json.dumps(_search_documents(query, n_results), default=str)

    @mcp.tool()
    def calculate_metrics(metric: str, params: str = "{}") -> str:
        """
        Calculate a predefined business metric.
        Available metrics: revenue_growth, top_products, customer_segments, regional_performance
        """
        try:
            p = json.loads(params)
        except Exception:
            p = {}
        return json.dumps(_calculate_metrics(metric, p), default=str)

    if __name__ == "__main__":
        port = int(os.getenv("MCP_PORT", 8090))
        mcp.run(transport="http", host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════════════════════
# Minimal HTTP shim (fallback when fastmcp is not installed)
# ══════════════════════════════════════════════════════════════════════════
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    TOOLS = {
        "query_database": lambda args: _run_sql(args.get("sql",""), args.get("limit",100)),
        "get_schema_info": lambda args: _get_schema(),
        "search_documents": lambda args: _search_documents(args.get("query",""), args.get("n_results",5)),
        "calculate_metrics": lambda args: _calculate_metrics(args.get("metric",""), args.get("params",{})),
    }

    class MCPHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[MCP] {fmt % args}")

        def _json(self, data, status=200):
            body = json.dumps(data, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/tools":
                tools_list = [
                    {"name":"query_database","description":"Run a read-only SQL SELECT query."},
                    {"name":"get_schema_info","description":"Return full DB schema."},
                    {"name":"search_documents","description":"Semantic document search."},
                    {"name":"calculate_metrics","description":"Calculate business metrics."},
                ]
                self._json({"tools": tools_list})
            elif self.path == "/health":
                self._json({"status":"ok"})
            else:
                self._json({"error":"Not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            tool = body.get("tool","")
            args = body.get("arguments",{})
            fn = TOOLS.get(tool)
            if fn:
                self._json({"result": fn(args)})
            else:
                self._json({"error": f"Unknown tool: {tool}"}, 400)

    if __name__ == "__main__":
        port = int(os.getenv("MCP_PORT", 8090))
        print(f"[MCP] Starting HTTP server on port {port}")
        HTTPServer(("0.0.0.0", port), MCPHandler).serve_forever()
