# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

A RAG-based chatbot with role-based access control (RBAC) for a company intranet. Six roles (Finance, Marketing, HR, Engineering, C-Level, Employee) each receive answers grounded only in documents they are authorized to see. Every response cites its source document and section. The backend is a Python FastAPI app (managed with `uv`); the frontend is a React TypeScript chat UI.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Backend language |
| uv | Python package manager and project runner |
| FastAPI | REST API framework |
| LangChain | RAG pipeline orchestration |
| Groq (Llama 3.1 70B) | LLM for response generation |
| Google `text-embedding-004` | Document and query embeddings (768-dim) |
| Pinecone | Vector database with metadata filtering for RBAC |
| python-jose + passlib | JWT auth and bcrypt password hashing |
| Langsmith | Query tracing and observability |
| Ragas | RAG evaluation metrics |
| React 18 + TypeScript | Chat frontend |
| Axios | HTTP client in frontend |

---

## Commands

```bash
# Backend — install dependencies
cd backend && uv sync

# Backend — start dev server
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Backend — run ingestion (one-time, requires .env)
cd backend && uv run python -m ingestion.ingest

# Backend — run Ragas evaluation
cd backend && uv run python -m ingestion.evaluate

# Frontend — install dependencies
cd frontend && npm install

# Frontend — start dev server
cd frontend && npm start

# Frontend — build for production
cd frontend && npm run build
```

---

## Project Structure

```
rag_project/
├── PRD.md                        # Product Requirements Document
├── CLAUDE.md                     # This file
├── resources/
│   └── data/                     # Source documents — DO NOT MODIFY
│       ├── finance/              # financial_summary.md, quarterly_financial_report.md
│       ├── marketing/            # 5 marketing report MDs
│       ├── hr/                   # hr_data.csv
│       ├── engineering/          # engineering_master_doc.md
│       └── general/              # employee_handbook.md
├── backend/
│   ├── pyproject.toml            # uv dependencies
│   ├── .env                      # secrets (gitignored)
│   ├── .env.example              # template (committed)
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router mounts
│   │   ├── config.py             # Pydantic settings from env vars
│   │   ├── auth/
│   │   │   ├── router.py         # POST /auth/login, GET /auth/me
│   │   │   ├── models.py         # Pydantic schemas (User, Token)
│   │   │   └── service.py        # JWT create/verify, user store, bcrypt
│   │   ├── chat/
│   │   │   ├── router.py         # POST /chat/query
│   │   │   └── rag_service.py    # Full RAG pipeline
│   │   ├── rbac/
│   │   │   └── permissions.py    # ROLE_PERMISSIONS + get_allowed_departments()
│   │   └── vector_store/
│   │       └── pinecone_client.py # Pinecone init + RBAC-filtered query
│   └── ingestion/
│       ├── ingest.py             # One-time ingestion entry point
│       ├── loaders.py            # MD + CSV document loaders
│       ├── chunker.py            # Chunking + metadata tagging
│       └── evaluate.py           # Ragas evaluation script
└── frontend/
    ├── package.json
    └── src/
        ├── App.tsx
        ├── contexts/AuthContext.tsx  # JWT storage, login/logout
        ├── services/api.ts           # Axios instance with auth header
        └── components/
            ├── Login.tsx
            ├── Chat.tsx
            ├── MessageBubble.tsx
            └── SourceCitation.tsx
```

---

## Architecture

**Data flow for a query:**
```
React UI → POST /chat/query (JWT)
         → get_current_user() extracts role from JWT
         → get_allowed_departments(role) → list of permitted dept tags
         → embed query with Google text-embedding-004
         → Pinecone query with filter: {department: {$in: allowed_depts}}
         → top-5 chunks returned
         → LangChain chain: chunks + prompt → Groq Llama 3.1 70B
         → response + source citations returned
         → Langsmith traces entire chain
```

**RBAC is enforced at the retrieval layer** — the Pinecone metadata filter is applied server-side before any content reaches the LLM. The LLM never sees unauthorized documents.

---

## Code Patterns

### Naming Conventions
- Python files: `snake_case.py`
- Python functions/variables: `snake_case`
- Python classes: `PascalCase`
- TypeScript components: `PascalCase.tsx`
- TypeScript utilities: `camelCase.ts`

### RBAC Pattern
- Role is always extracted from JWT — never from the request body or query params
- `get_allowed_departments(role)` in `rbac/permissions.py` is the single source of truth
- Pinecone filter is constructed from allowed departments — never bypassed

### FastAPI Patterns
- Auth dependency: `current_user: dict = Depends(get_current_user)` on protected routes
- Settings loaded once via `config.py` Pydantic `BaseSettings`
- Routers prefixed: `/auth`, `/chat`

### LangChain Patterns
- Use `RetrievalQAWithSourcesChain` to get answer + source metadata in one call
- Wrap chain with `@traceable` for Langsmith
- Prompt instructs LLM to answer only from context and cite sources

### Error Handling
- FastAPI `HTTPException` for all API errors (401, 403, 422, 500)
- LLM fallback message if no relevant context found: `"I don't have access to that information."`

---

## RBAC Access Matrix

| Role | finance | marketing | hr | engineering | general |
|------|---------|-----------|-----|-------------|---------|
| finance | ✅ | ❌ | ❌ | ❌ | ✅ |
| marketing | ❌ | ✅ | ❌ | ❌ | ✅ |
| hr | ❌ | ❌ | ✅ | ❌ | ✅ |
| engineering | ❌ | ❌ | ❌ | ✅ | ✅ |
| c_level | ✅ | ✅ | ✅ | ✅ | ✅ |
| employee | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Demo Users

| Username | Password | Role |
|----------|----------|------|
| alice | pass123 | finance |
| bob | pass123 | marketing |
| carol | pass123 | hr |
| dave | pass123 | engineering |
| eve | pass123 | c_level |
| frank | pass123 | employee |

---

## Testing & Validation

```bash
# Verify backend imports are clean
cd backend && uv run python -c "import fastapi, langchain, pinecone"

# Test auth endpoint
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "pass123"}'

# Test RBAC enforcement (employee should not see financial data)
# 1. Login as frank → get token
# 2. POST /chat/query with query "What is our gross margin?"
# 3. Expect: "I don't have access to that information."

# Run Ragas evaluation
cd backend && uv run python -m ingestion.evaluate
```

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/rbac/permissions.py` | Role → department mapping — edit here to change access rules |
| `backend/app/chat/rag_service.py` | Core RAG pipeline — retrieval + generation |
| `backend/app/auth/service.py` | JWT logic + demo user store |
| `backend/ingestion/ingest.py` | Run this once to populate Pinecone |
| `backend/app/config.py` | All env var config in one place |
| `PRD.md` | Full product requirements |
| `.env.example` | Required environment variables |

---

## On-Demand Context

| Topic | File |
|-------|------|
| Full product requirements | `PRD.md` |
| Implementation plan | `.claude/plans/immutable-greeting-fountain.md` |
| Source documents | `resources/data/` |

---

## Notes

- **Never modify files in `resources/data/`** — these are the source of truth for ingestion
- **Run ingestion once** after setting up `.env` — re-running will create duplicate vectors in Pinecone
- **Pinecone index dimension is 768** (Google text-embedding-004) — do not change without re-ingesting
- **`.env` is gitignored** — copy `.env.example` → `.env` and fill in real keys before running
- RBAC is enforced server-side at retrieval — do not add role checks in the frontend as a substitute
