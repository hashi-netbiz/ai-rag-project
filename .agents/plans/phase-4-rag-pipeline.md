# Feature: Phase 4 — RAG Pipeline + FastAPI Wiring

The following plan should be complete. Validate API signatures against installed packages before implementing — langchain 1.2.13, langchain-groq 1.1.2, langchain-pinecone 0.2.13, langchain-core 1.2.22, langsmith 0.7.22.

**CRITICAL**: Do NOT use `text-embedding-004`. That model is unavailable for this Google API key. Use `models/gemini-embedding-001` with `output_dimensionality=768` — confirmed working in Phase 2.

**CRITICAL**: Do NOT use `llama-3.1-70b-versatile` — decommissioned by Groq. Use `llama-3.3-70b-versatile`.

## Feature Description

Implement the full RAG pipeline: authenticated query endpoint, RBAC-filtered Pinecone retrieval, Google embedding for queries, Groq LLM generation, and Langsmith tracing. Wire the chat router into `main.py`. After this phase the full backend is functional end-to-end.

## User Story

As an authenticated user,
I want to POST a natural language query and receive an answer grounded in documents I'm authorized to see with source citations,
So that I can get role-appropriate answers without manual document searching.

## Problem Statement

`pinecone_client.py`, `rag_service.py`, and `chat/router.py` are all stubs. `main.py` is missing the chat router. No query can be processed.

## Solution Statement

Implement in dependency order:
1. `pinecone_client.py` — lazy vectorstore factory + filtered retriever helper
2. `rag_service.py` — LCEL chain: embed query → retrieve (RBAC filter) → generate (Groq) → parse sources; wrapped with `@traceable`
3. `chat/router.py` — thin HTTP layer using `get_current_user` dependency
4. Update `main.py` — mount chat router + set Langsmith env vars from settings

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `backend/app/vector_store/`, `backend/app/chat/`, `backend/app/main.py`
**Dependencies**: All installed — langchain-groq 1.1.2, langchain-pinecone 0.2.13, langchain-google-genai 4.2.1, langsmith 0.7.22

---

## CONTEXT REFERENCES

### Already Implemented — Do NOT Modify
- `backend/app/config.py` — `settings` singleton with all API keys
- `backend/app/rbac/permissions.py` — `get_allowed_departments(role) -> list[str]`
- `backend/app/auth/service.py` — `get_current_user` dependency returns `{"username": str, "role": str}`
- `backend/app/main.py` — FastAPI app with CORS, auth router already mounted

### Files to Implement
- `backend/app/vector_store/pinecone_client.py`
- `backend/app/chat/rag_service.py`
- `backend/app/chat/router.py`

### File to Update
- `backend/app/main.py` — add chat router import + mount, set Langsmith env vars

### Verified API Signatures

```python
# Embedding — CONFIRMED WORKING (Phase 2)
from langchain_google_genai import GoogleGenerativeAIEmbeddings
GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",   # NOT "models/text-embedding-004" — unavailable
    google_api_key=str,
    output_dimensionality=768,
)

# LangChain LCEL
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Groq LLM — llama-3.1-70b-versatile DECOMMISSIONED, use 3.3
from langchain_groq import ChatGroq
ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=str)

# Pinecone vectorstore + RBAC-filtered retriever
from langchain_pinecone import PineconeVectorStore
vectorstore.as_retriever(search_kwargs={"k": 5, "filter": {"department": {"$in": list}}})

# Langsmith tracing
from langsmith import traceable
@traceable
```

### Metadata Shape on Pinecone Chunks (from Phase 2)

```python
{
    "department": "finance",
    "source_file": "financial_summary.md",
    "section": "Q3 Summary",          # may be ""
    "subsection": "",
    "doc_type": "markdown" | "csv",
    "chunk_id": "financial_summary_0",
}
```

### PRD API Spec

```json
POST /chat/query
Authorization: Bearer <token>
{"query": "What was our Q3 gross margin?"}

Response 200:
{
  "answer": "The Q3 2024 gross margin was 62%...",
  "sources": [{"file": "quarterly_financial_report.md", "section": "Q3 2024 Financial Summary"}],
  "role": "finance"
}
```

### Langsmith Configuration Note

`pydantic-settings` loads `.env` into the `settings` object but does NOT update `os.environ`. LangChain reads tracing config from `os.environ`. Set these in `main.py` at startup:

```python
import os
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
```

---

## STEP-BY-STEP TASKS

### TASK 1 — IMPLEMENT `backend/app/vector_store/pinecone_client.py`

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.vectorstores import VectorStoreRetriever

from app.config import settings

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSION = 768


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.google_api_key,
        output_dimensionality=EMBEDDING_DIMENSION,
    )


def get_vectorstore() -> PineconeVectorStore:
    return PineconeVectorStore(
        index_name=settings.pinecone_index_name,
        embedding=_get_embeddings(),
        pinecone_api_key=settings.pinecone_api_key,
    )


def get_retriever(allowed_departments: list[str], k: int = 5) -> VectorStoreRetriever:
    """Return a Pinecone retriever pre-filtered to the given departments."""
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(
        search_kwargs={
            "k": k,
            "filter": {"department": {"$in": allowed_departments}},
        }
    )
```

- **GOTCHA**: All functions — not called at module import time. Avoids import-time API calls.
- **VALIDATE**: `cd backend && uv run python -c "from app.vector_store.pinecone_client import get_retriever; print('OK')"`

---

### TASK 2 — IMPLEMENT `backend/app/chat/rag_service.py`

```python
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langsmith import traceable

from app.config import settings
from app.rbac.permissions import get_allowed_departments
from app.vector_store.pinecone_client import get_retriever

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a company knowledge assistant. Answer questions based ONLY on the provided context.
If the context does not contain relevant information to answer the question, respond with exactly:
"I don't have access to that information."
Do not use any knowledge outside of the provided context. Be concise and factual."""

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])


def _get_llm() -> ChatGroq:
    return ChatGroq(model=GROQ_MODEL, groq_api_key=settings.groq_api_key)


def _extract_sources(docs: list[Document]) -> list[dict]:
    seen: set[tuple] = set()
    sources: list[dict] = []
    for doc in docs:
        file = doc.metadata.get("source_file", "")
        section = doc.metadata.get("section", "")
        key = (file, section)
        if key not in seen:
            seen.add(key)
            sources.append({"file": file, "section": section})
    return sources


@traceable
def rag_query(query: str, role: str) -> dict:
    """Run a role-restricted RAG query. Returns answer, sources, and role."""
    allowed_depts = get_allowed_departments(role)

    if not allowed_depts:
        return {"answer": "I don't have access to that information.", "sources": [], "role": role}

    retriever = get_retriever(allowed_depts)
    docs = retriever.invoke(query)

    if not docs:
        return {"answer": "I don't have access to that information.", "sources": [], "role": role}

    context = "\n\n---\n\n".join(doc.page_content for doc in docs)
    chain = _prompt | _get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context, "question": query})

    return {"answer": answer, "sources": _extract_sources(docs), "role": role}
```

- **GOTCHA**: LCEL used instead of `RetrievalQAWithSourcesChain` — our metadata uses `source_file` not `source`.
- **VALIDATE**: `cd backend && uv run python -c "from app.chat.rag_service import rag_query; print('OK')"`

---

### TASK 3 — IMPLEMENT `backend/app/chat/router.py`

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.service import get_current_user
from app.chat.rag_service import rag_query

router = APIRouter(prefix="/chat", tags=["chat"])


class QueryRequest(BaseModel):
    query: str


class SourceCitation(BaseModel):
    file: str
    section: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    role: str


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> QueryResponse:
    role = current_user["role"]
    result = rag_query(query=request.query, role=role)
    return QueryResponse(
        answer=result["answer"],
        sources=[SourceCitation(**s) for s in result["sources"]],
        role=result["role"],
    )
```

- **NOTE**: Role always from JWT — never from request body.

---

### TASK 4 — UPDATE `backend/app/main.py`

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

from app.auth.router import router as auth_router
from app.chat.router import router as chat_router

app = FastAPI(title="RAG RBAC Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

---

## VALIDATION COMMANDS

### Level 1: Import chain

```bash
cd backend && uv run python -c "
from app.vector_store.pinecone_client import get_retriever
from app.chat.rag_service import rag_query
from app.chat.router import router
from app.main import app
routes = [r.path for r in app.routes]
assert '/chat/query' in routes
print('ALL IMPORTS OK')
print('Routes:', routes)
"
```

### Level 2: RBAC logic

```bash
cd backend && uv run python -c "
from app.rbac.permissions import get_allowed_departments
assert get_allowed_departments('finance') == ['finance', 'general']
assert get_allowed_departments('employee') == ['general']
assert get_allowed_departments('c_level') == ['finance','marketing','hr','engineering','general']
print('RBAC logic OK')
"
```

### Level 3: Live E2E

```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3

ALICE_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/chat/query \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the gross margin?"}'
```

---

## ACCEPTANCE CRITERIA

- [ ] `POST /chat/query` as alice (finance) returns answer + sources from finance/general docs
- [ ] `POST /chat/query` as frank (employee) asking about financials returns denial message
- [ ] `POST /chat/query` without token returns 401
- [ ] `sources` array contains `file` and `section` fields
- [ ] `role` field in response matches the authenticated user's role
- [ ] Langsmith traces visible at smith.langchain.com
- [ ] Level 1–2 validation commands pass

---

## NOTES

**LCEL over RetrievalQAWithSourcesChain**: The PRD specifies `RetrievalQAWithSourcesChain` but that requires a `source` metadata key. Our Pinecone chunks use `source_file` (Phase 2). LCEL is the modern LangChain 0.2+ approach.

**Lazy initialization**: `get_vectorstore()` and `_get_llm()` are called inside functions, not at module level. App starts cleanly even if API keys are temporarily missing.

**Groq model**: `llama-3.3-70b-versatile` replaces `llama-3.1-70b-versatile` (decommissioned). Confirmed working 2026-03-24.

**Embedding model**: `models/gemini-embedding-001` with `output_dimensionality=768` replaces `text-embedding-004` (unavailable for this API key). Confirmed working in Phase 2.
