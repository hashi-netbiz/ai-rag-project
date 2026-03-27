# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

A RAG-based chatbot with role-based access control (RBAC) for a company intranet. Six roles (Finance, Marketing, HR, Engineering, C-Level, Employee) each receive answers grounded only in documents they are authorized to see. Every response cites its source document and section. The backend is a Python FastAPI app (managed with `uv`); the frontend is a Next.js 15 App Router chat UI. A full DevSecOps CI/CD pipeline runs on GitHub Actions.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Backend language |
| uv | Python package manager and project runner |
| FastAPI | REST API framework |
| LangChain (LCEL) | RAG pipeline orchestration |
| Groq (Llama 3.3 70B) | LLM for response generation |
| Google `gemini-embedding-2-preview` | Document and query embeddings (768-dim) |
| Pinecone | Vector database + native reranker (`bge-reranker-v2-m3`) |
| python-jose + passlib | JWT auth and bcrypt password hashing |
| Langsmith | Query tracing and observability |
| Ragas | RAG evaluation metrics |
| pytest + pytest-cov | Backend unit tests (52 tests, 89% coverage) |
| Next.js 15 + React 19 + TypeScript | Chat frontend (App Router) |
| Tailwind CSS v4 + shadcn/ui | Frontend styling and components |
| Zustand | Frontend state management |
| Docker + docker-compose | Containerisation |
| GitHub Actions | CI/CD pipeline (DevSecOps) |

---

## Commands

```bash
# Backend — install dependencies (prod)
cd backend && uv sync

# Backend — install dependencies (with dev/test tools)
cd backend && uv sync --group dev

# Backend — start dev server
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Backend — run unit tests
cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Backend — run ingestion (one-time, requires .env)
cd backend && uv run python -m ingestion.ingest

# Backend — run Ragas evaluation
cd backend && uv run python -m ingestion.evaluate

# Frontend — install dependencies
cd frontend-next && npm install

# Frontend — start dev server (port 3001)
cd frontend-next && npm run dev

# Frontend — build for production
cd frontend-next && npm run build

# Frontend — type check
cd frontend-next && npm run type-check

# Docker — build and run full stack
docker compose build
docker compose up -d

# E2E regression suite (requires backend on :8000, frontend on :3001)
bash test_e2e.sh
```

---

## Project Structure

```
rag_project/
├── PRD.md                        # Product Requirements Document
├── CLAUDE.md                     # This file
├── sonar-project.properties      # SonarCloud SAST config
├── Dockerfile.backend            # Python 3.11-slim + uv
├── Dockerfile.frontend           # Multi-stage Node 20 Alpine (standalone)
├── docker-compose.yml            # Full stack with healthchecks
├── test_e2e.sh                   # 42-test E2E regression suite
├── .github/
│   └── workflows/
│       └── ci-cd.yml             # DevSecOps pipeline (7 stages)
├── resources/
│   └── data/                     # Source documents — DO NOT MODIFY
│       ├── finance/              # financial_summary.md, quarterly_financial_report.md
│       ├── marketing/            # 5 marketing report MDs
│       ├── hr/                   # hr_data.csv
│       ├── engineering/          # engineering_master_doc.md
│       └── general/              # employee_handbook.md
├── backend/
│   ├── pyproject.toml            # uv dependencies (prod + dev group)
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
│   │   │   └── rag_service.py    # Full RAG pipeline (retrieve → rerank → generate)
│   │   ├── rbac/
│   │   │   └── permissions.py    # ROLE_PERMISSIONS + get_allowed_departments()
│   │   └── vector_store/
│   │       └── pinecone_client.py # Pinecone init + RBAC-filtered retriever (k=6)
│   ├── tests/
│   │   ├── conftest.py           # Fixtures (client, alice_token, frank_token)
│   │   ├── test_rbac.py          # RBAC permission logic tests
│   │   ├── test_auth.py          # Auth service + JWT tests
│   │   ├── test_rag_service.py   # _extract_sources, _rerank unit tests
│   │   └── test_routes.py        # FastAPI route integration tests
│   └── ingestion/
│       ├── ingest.py             # One-time ingestion entry point
│       ├── loaders.py            # MD + CSV document loaders
│       ├── chunker.py            # Chunking + metadata tagging
│       └── evaluate.py           # Ragas evaluation script
└── frontend-next/                # Next.js 15 App Router frontend (port 3001)
    ├── app/
    │   ├── page.tsx              # Login page (/)
    │   ├── chat/page.tsx         # Main chat page (/chat)
    │   └── api/                  # Proxy routes → FastAPI
    ├── components/               # MessageBubble, RoleBadge, SourceCitation, etc.
    ├── stores/                   # Zustand auth + chat stores
    ├── lib/
    │   ├── apiClient.ts          # fetch-based API client
    │   └── constants.ts          # FASTAPI_BASE_URL (env-driven), role config
    └── types/api.ts              # Shared TypeScript types
```

---

## Architecture

**Data flow for a query:**
```
Next.js UI (port 3001) → /api/chat/query (proxy)
         → FastAPI POST /chat/query (JWT)
         → get_current_user() extracts role from JWT
         → get_allowed_departments(role) → list of permitted dept tags
         → embed query with Google gemini-embedding-2-preview (768-dim)
         → Pinecone query with filter: {department: {$in: allowed_depts}}, k=6
         → Pinecone rerank: bge-reranker-v2-m3 → top 3 chunks
         → LCEL chain: chunks + prompt → Groq Llama 3.3 70B
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

- Use LCEL (`_prompt | _get_llm() | StrOutputParser()`) — not `RetrievalQAWithSourcesChain` (requires `source` key; our metadata uses `source_file`)
- Wrap the top-level function with `@traceable` for Langsmith
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
# Run backend unit tests (52 tests, no real API keys needed)
cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing

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

# Run E2E regression suite (requires both services running)
bash test_e2e.sh  # expects 42/42 passed

# Run Ragas evaluation
cd backend && uv run python -m ingestion.evaluate

# Build and run Docker stack
docker compose build && docker compose up -d
```

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/rbac/permissions.py` | Role → department mapping — edit here to change access rules |
| `backend/app/chat/rag_service.py` | Core RAG pipeline — retrieve → rerank → generate |
| `backend/app/vector_store/pinecone_client.py` | RBAC-filtered Pinecone retriever (k=6) |
| `backend/app/auth/service.py` | JWT logic + demo user store |
| `backend/tests/` | Unit tests — 52 tests, 89% coverage |
| `backend/ingestion/ingest.py` | Run this once to populate Pinecone |
| `backend/app/config.py` | All env var config in one place |
| `.github/workflows/ci-cd.yml` | GitHub Actions DevSecOps pipeline |
| `Dockerfile.backend` / `Dockerfile.frontend` | Container images |
| `docker-compose.yml` | Full stack orchestration |
| `sonar-project.properties` | SonarCloud SAST config (update projectKey/org) |
| `PRD.md` | Full product requirements |
| `.env.example` | Required environment variables |

---

## On-Demand Context

| Topic | File |
|-------|------|
| Full product requirements | `PRD.md` |
| RAG pipeline plan | `.agents/plans/phase-4-rag-pipeline.md` |
| CI/CD pipeline plan | `.claude/plans/frolicking-tickling-turtle.md` |
| Source documents | `resources/data/` |

---

## Notes

- **Never modify files in `resources/data/`** — these are the source of truth for ingestion
- **Run ingestion once** after setting up `.env` — re-running will create duplicate vectors in Pinecone
- **Pinecone index dimension is 768** (`gemini-embedding-2-preview`) — do not change without re-ingesting
- **`.env` is gitignored** — copy `.env.example` → `.env` and fill in real keys before running
- RBAC is enforced server-side at retrieval — do not add role checks in the frontend as a substitute
- **LLM:** `llama-3.3-70b-versatile` — do NOT use `llama-3.1-70b-versatile` (decommissioned by Groq)
- **Embedding:** `models/gemini-embedding-2-preview` — do NOT use `text-embedding-004` or `gemini-embedding-001`
- **Frontend runs on port 3001** — CORS in `main.py` already allows both 3000 and 3001
- **`sonar-project.properties`** — replace `YOUR_SONAR_PROJECT_KEY` and `YOUR_SONAR_ORG` before SonarCloud runs
- **`GITOPS_REPO` secret** — not yet set in GitHub Actions; required for the gitops-update job stub
