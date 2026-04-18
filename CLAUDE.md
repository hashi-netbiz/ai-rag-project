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
| pytest + pytest-cov | Backend unit tests (154 tests, 99% coverage) |
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
│       ├── ci.yml                # PR validation (secret scan, SAST, SCA, tests, Docker build, Trivy)
│       ├── deploy.yml            # Post-merge deploy (E2E → ECR push → DAST → GitOps update)
│       └── promote-prod.yml      # Manual production promotion with GitHub Environment approval gate
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
│   │   │   ├── router.py         # POST /chat/query (input guardrails wired here)
│   │   │   └── rag_service.py    # Full RAG pipeline (retrieve → rerank → guardrails → generate)
│   │   ├── guardrails/           # Multi-layer guardrail module
│   │   │   ├── __init__.py       # Re-exports runner functions + event models
│   │   │   ├── models.py         # GuardrailAction enum, GuardrailEvent dataclass
│   │   │   ├── input_guards.py   # check_query_length, check_prompt_injection, check_pii
│   │   │   ├── context_guards.py # sanitize_context_docs, check_source_trust, check_relevance_threshold
│   │   │   ├── output_guards.py  # check_refusal, check_faithfulness, check_response_length
│   │   │   └── runner.py         # run_input/context/output_guardrails orchestrators
│   │   ├── rbac/
│   │   │   └── permissions.py    # ROLE_PERMISSIONS + get_allowed_departments()
│   │   └── vector_store/
│   │       └── pinecone_client.py # Pinecone init + RBAC-filtered retriever (k=6)
│   ├── tests/
│   │   ├── conftest.py           # Fixtures (client, alice_token, frank_token)
│   │   ├── test_rbac.py          # RBAC permission logic tests
│   │   ├── test_auth.py          # Auth service + JWT tests
│   │   ├── test_rag_service.py   # _extract_sources, _rerank unit tests
│   │   ├── test_routes.py        # FastAPI route integration tests
│   │   └── test_guardrails.py    # Guardrail unit tests (81 tests, all layers + runners)
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
         → [A] Input guardrails: length check → injection detection → PII sanitize
         → get_allowed_departments(role) → list of permitted dept tags
         → embed query with Google gemini-embedding-2-preview (768-dim)
         → Pinecone query with filter: {department: {$in: allowed_depts}}, k=6
         → Pinecone rerank: bge-reranker-v2-m3 → top 3 chunks
         → [B] Context guardrails: source trust → relevance threshold → context sanitize
         → LCEL chain: chunks + prompt → Groq Llama 3.3 70B
         → [C] Output guardrails: refusal detection → faithfulness → length cap
         → response + source citations + guardrail_flags returned
         → Langsmith traces entire chain (guardrail flags attached as metadata)
```

**RBAC is enforced at the retrieval layer** — the Pinecone metadata filter is applied server-side before any content reaches the LLM. The LLM never sees unauthorized documents.

**Guardrails are defense-in-depth** — three layers enforce safety at input, context, and output. Every API response includes a `guardrail_flags` list (empty on clean requests) indicating which checks fired.

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

### Guardrail Patterns

- Three runner functions in `guardrails/runner.py`: `run_input_guardrails`, `run_context_guardrails`, `run_output_guardrails`
- Input guardrails run in `chat/router.py` (HTTP boundary) — hard blocks raise `HTTPException(400)`; PII is sanitized and the redacted query continues
- Context guardrails run in `chat/rag_service.py` after `_rerank()` — source trust violations raise `HTTPException(403)`; low relevance triggers the canned fallback
- Output guardrails run in `chat/rag_service.py` after `chain.invoke()` — all are non-blocking (flag or truncate only)
- `QueryResponse` includes `guardrail_flags: list[str] = []` — empty on clean requests; contains check names when a guardrail fired
- All guardrail thresholds are config-driven via `config.py` (e.g. `GUARDRAIL_RELEVANCE_THRESHOLD=0.1`); defaults are safe/permissive

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
# Run backend unit tests (154 tests, no real API keys needed)
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
| `backend/app/chat/rag_service.py` | Core RAG pipeline — retrieve → rerank → guardrails → generate |
| `backend/app/guardrails/` | Multi-layer guardrail module (input, context, output) |
| `backend/app/guardrails/runner.py` | Orchestrators — edit here to add/remove guardrail checks |
| `backend/app/guardrails/input_guards.py` | Injection patterns + PII patterns — edit to tune detection |
| `backend/app/vector_store/pinecone_client.py` | RBAC-filtered Pinecone retriever (k=6) |
| `backend/app/auth/service.py` | JWT logic + demo user store |
| `backend/tests/` | Unit tests — 154 tests, 99% coverage |
| `backend/tests/test_guardrails.py` | Guardrail unit tests — 81 tests, all layers + runners |
| `backend/ingestion/ingest.py` | Run this once to populate Pinecone |
| `backend/app/config.py` | All env var config in one place (incl. `ALLOWED_ORIGINS`) |
| `.github/workflows/ci.yml` | PR validation workflow |
| `.github/workflows/deploy.yml` | Post-merge deploy workflow (ECR push + GitOps update) |
| `.github/workflows/promote-prod.yml` | Manual production promotion with approval gate |
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
| GitOps CI/CD requirements | `NEW_PRD.md` |
| RAG pipeline plan | `.agents/plans/phase-4-rag-pipeline.md` |
| GitOps CI/CD plan | `.agents/plans/phase-4-gitops-cicd.md` |
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
- **Frontend runs on port 3001** — CORS origins are env-var driven via `ALLOWED_ORIGINS` in `.env`; defaults to `http://localhost:3000,http://localhost:3001`
- **`sonar-project.properties`** — replace `YOUR_SONAR_PROJECT_KEY` and `YOUR_SONAR_ORG` before SonarCloud runs
- **`GITOPS_REPO` / `GITOPS_TOKEN` secrets** — required by `deploy.yml` (gitops-update job) and `promote-prod.yml`; must be set in GitHub Actions repo secrets
- **GitHub Environment `production`** — must be created in GitHub repo settings with required reviewer(s) for `promote-prod.yml` approval gate to work
- **ECR tag mutability** — backend and frontend ECR repos must be set to `MUTABLE` to allow `staging-latest` re-pushes; production always uses the immutable `sha-<github.sha>` tag
