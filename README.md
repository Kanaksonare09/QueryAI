# QueryAI V2 — Offline Conversational AI Database Analyst

[![GitHub Repo](https://img.shields.io/badge/GitHub-Kanaksonare09%2FQueryAI-blue?logo=github)](https://github.com/Kanaksonare09/QueryAI)


> **A fully offline conversational AI data analyst** capable of understanding natural-language questions, planning database queries, detecting ambiguity, maintaining analytical context across follow-up questions, and performing evidence-based root-cause investigations — while securely querying private MySQL databases.

QueryAI V2 is a production-quality, **fully offline** AI assistant that goes far beyond basic Text-to-SQL. It reasons about your data across multi-turn conversations, intelligently plans queries, detects vague questions, and can autonomously investigate the root cause of metric changes — all powered by local Ollama inference with zero cloud APIs.

---

## ✨ What It Does (User Perspective)

```
You type:  "Compare revenue between top 3 regions as a chart"
    ↓
QueryAI:   📊 Bar chart  +  📝 Business insight  +  🔽 SQL used  +  🏷️ Source tables
```

| You ask | You get |
|---|---|
| Revenue by region | Bar chart + ranking |
| Monthly revenue trend | Line chart + growth insight |
| Total revenue this year | KPI card with big bold number |
| Top customers by value | Ranked table |
| Why did revenue drop? | **Root-cause investigation with driver ranking** |
| Only show Europe (follow-up) | **Context-aware query modification** |

**No SQL knowledge needed. No cloud. No data ever leaves your machine.**

---

## 🆕 V2 Intelligence Features

### 1. 🔎 Root-Cause Investigation Mode
Ask a "why" question and QueryAI autonomously plans and executes a multi-query investigation:
```
User: Why did revenue decrease in Q3?

QueryAI Investigation:
→ Baseline: Revenue ↓18.3% (Q2 → Q3)
→ Region breakdown: Europe ↓31% (47% contribution)
→ Segment breakdown: Enterprise ↓24% (31% contribution)
→ Product breakdown: Product A ↓42% (19% contribution)

Conclusion: Europe was the largest measurable driver of the decline.
```

### 2. 🧠 Conversational SQL Memory
```
User: Show top 5 customers by revenue.      → [Results]
User: Only from Europe.                      → [Filtered using context]
User: Compare them with last year.           → [Comparison query auto-built]
User: Make it a bar chart.                   → [Chart type updated, no re-query]
```

### 3. 🎯 Intent Detection & Ambiguity Handling
```
User: Show our best customers.

QueryAI: How should I define "best"?
  ○ Highest total revenue
  ○ Most orders
  ○ Highest average order value
  ○ Highest profit contribution
```

### 4. 📐 AI Query Planning
Generates a structured query plan before SQL, including: intent, metrics, dimensions, required tables, and recommended visualization — ensuring deterministic, reproducible SQL generation.

### 5. 🗄️ Hybrid Schema RAG
Combines ChromaDB vector search + keyword entity matching + FK graph traversal to select only the most relevant schema elements, reducing prompt size and improving SQL accuracy.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ http://localhost:3000
┌──────────────────────▼──────────────────────────────────────┐
│              Frontend  (React + Vite)                       │
│   ChatWindow · Recharts · Query History · Status Sidebar    │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /api/v1/chat/message
┌──────────────────────▼──────────────────────────────────────┐
│              Backend  (FastAPI · port 8080)                  │
│                                                             │
│  ┌────────────┐   ┌─────────────┐   ┌──────────────────┐   │
│  │ Schema RAG │   │ SQL Generator│   │ Insights Engine  │   │
│  │ ChromaDB   │──▶│  Ollama LLM │──▶│  Ollama LLM      │   │
│  │ port 8000  │   │ qwen2.5:7b  │   │  qwen2.5:7b      │   │
│  └────────────┘   └──────┬──────┘   └──────────────────┘   │
│                          │                                   │
│                   ┌──────▼──────┐                           │
│                   │  Security   │                           │
│                   │  Validator  │ ← 4-layer SQL safety      │
│                   └──────┬──────┘                           │
│                          │                                   │
│                   ┌──────▼──────┐                           │
│                   │   MySQL     │                           │
│                   │  port 3306  │ ← Real business data      │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### Services

| Service | Stack | Port | Role |
|---|---|---|---|
| **Frontend** | React 18 + Vite | **3000** | Chat UI, charts, history |
| **Backend API** | FastAPI + Python | **8080** | Orchestrates full pipeline |
| **Vector Store** | ChromaDB | **8000** | Schema similarity search (RAG) |
| **LLM + Embeddings** | Ollama | **11434** | SQL generation, insights, embeddings |
| **Analytics DB** | MySQL 8.0 | **3306** | Live business data |
| **Metadata DB** | SQLite (file) | — | Query history, conversations |

---

## 🔄 How It Works (Pipeline)

Every natural language question goes through this pipeline:

```
1. Schema RAG     — Find relevant tables via ChromaDB vector search
2. SQL Generator  — Ollama LLM writes a SELECT query from question + schema
3. Security Check — 4-layer validator (keyword blocklist → regex → AST → complexity)
4. SQL Executor   — Run against MySQL, serialize results
5. Auto-Corrector — If query fails, LLM retries with error context (×2)
6. Chart Picker   — Ollama recommends bar/line/pie/KPI based on result shape
7. Summarizer     — Ollama writes a 2–4 sentence business insight
8. Response       — JSON with chart_data, answer, sql_results, citations
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** and **Node.js 18+**
- **MySQL** running locally (port 3306)
- **Ollama** installed — [download here](https://ollama.com/download)

### 1. Pull Local Models

```bash
ollama pull qwen2.5:7b        # SQL generation + insights
ollama pull nomic-embed-text  # Schema embeddings for RAG
```

### 2. Set Up the Database

```bash
mysql -u root -p < database/schema.sql   # Create tables
mysql -u root -p < database/seed.sql     # Load demo data
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

Key variables:
```env
BIZ_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_assistant_demo
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

### 4. Start ChromaDB

```bash
mkdir -p storage/chroma_data
chroma run --path ./storage/chroma_data --host localhost --port 8000
```

### 5. Start the Backend

```bash
cd QueryAI/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 6. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

### 7. Open the App

```
http://localhost:3000
```

---

## 💡 Example Questions

```
"Compare revenue between top 3 regions as a chart"
"Show monthly revenue trend for 2025 as a line chart"
"Who are the top 5 customers by lifetime value?"
"What is total revenue this year?"
"Which products have the highest profit margin?"
"Compare Q1 vs Q2 revenue across all regions"
"Which department has the highest average salary?"
"Show all orders above $20,000 in 2025"
```

---

## 🛡️ Security — Read-Only Enforcement

The database is **read-only** from the chat interface. All generated SQL is validated through 4 layers before execution:

| Layer | Check |
|---|---|
| **1. Keyword Blocklist** | Blocks `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `GRANT` |
| **2. Regex Patterns** | Blocks `SLEEP()`, `BENCHMARK()`, `INTO OUTFILE`, stacked queries (`;`) |
| **3. AST Parsing** | SQL parsed into an abstract syntax tree — root node must be `SELECT` |
| **4. Complexity Guard** | Rejects queries with more than 10 JOINs |

If any layer fails → request is rejected and explained to the user. **The DB is never touched.**

---

## 📊 Demo Database

The seed data represents a fictional B2B software company **NexaCorp** with:

| Table | Records | Contains |
|---|---|---|
| `regions` | 6 | NA East/West, Europe West/Central, Asia Pacific, Latin America |
| `employees` | 8 | Sales reps, VP, CTO, CFO, Marketing Director |
| `customers` | 12 | Enterprise & SMB customers across all regions |
| `products` | 12 | Analytics, Security, Cloud, Consulting, Support packages |
| `categories` | 8 | Software, Hardware, Services sub-categories |
| `orders` | 45 | Real transactions from Q1 2024 → Q4 2025 |
| `order_items` | ~80 | Line items per order with quantity, price, discount |

---

## 🌐 API Reference

Base URL: `http://localhost:8080`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat/message` | Main chat endpoint (UI-optimized response) |
| `POST` | `/api/v1/query` | Direct pipeline — question → SQL → results |
| `POST` | `/api/v1/query/validate` | Validate SQL only (no execution) |
| `GET` | `/api/v1/schema` | Database schema metadata |
| `GET` | `/api/v1/history` | Query audit log |
| `GET` | `/api/v1/system/status` | Health of all services |

Interactive docs: [http://localhost:8080/api/docs](http://localhost:8080/api/docs)

---

## 📁 Project Structure

```
text-to-sql/
├── frontend/                   # React + Vite UI
│   └── src/
│       ├── components/         # ChatWindow, Sidebar, ChartBlock
│       └── hooks/              # useChat.js — API integration
│
├── QueryAI/backend/            # FastAPI backend
│   └── app/
│       ├── ai/                 # sql_generator, rag, insights, sql_corrector
│       ├── api/routes/         # chat, query, system endpoints
│       ├── database/           # connection, sql_executor
│       ├── security/           # sql_validator (4-layer)
│       └── main.py             # FastAPI app entry point
│
├── database/
│   ├── schema.sql              # MySQL table definitions
│   └── seed.sql                # Demo data (NexaCorp business data)
│
└── docs/
    └── architecture.md         # Detailed system design
```

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Recharts, Axios |
| **Backend** | Python, FastAPI, SQLAlchemy, Uvicorn, Structlog |
| **AI / LLM** | Ollama (`qwen2.5:7b`, `nomic-embed-text`) |
| **Vector Search** | ChromaDB |
| **SQL Safety** | sqlglot (AST parsing) |
| **Databases** | MySQL 8.0 (business data), SQLite (metadata) |
| **Testing** | pytest (19 tests — unit + integration) |

---

## 🧪 Running Tests

```bash
cd QueryAI/backend
pytest tests/ -v
```

Expected output: **19 passed** covering SQL safety, RAG retrieval, and API endpoints.

---

## 🔒 Privacy

All processing is **100% local**. No data, queries, or results are sent to any external service. The LLM runs on your machine via Ollama.
