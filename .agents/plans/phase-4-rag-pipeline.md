# Feature: Phase 4 — RAG Pipeline + FastAPI Wiring (with Reranking)

**Status:** Complete ✅

**CRITICAL**: Do NOT use `text-embedding-004` or `gemini-embedding-001`. Use `models/gemini-embedding-2-preview` with `output_dimensionality=768` — confirmed working.

**CRITICAL**: Do NOT use `llama-3.1-70b-versatile` — decommissioned by Groq. Use `llama-3.3-70b-versatile`.

## Feature Description

Implement the full RAG pipeline: authenticated query endpoint, RBAC-filtered Pinecone retrieval (k=10), Pinecone native reranking (`bge-reranker-v2-m3`, top 3), Google embedding for queries, Groq LLM generation, and Langsmith tracing. Wire the chat router into `main.py`.

## User Story

As an authenticated user,
I want to POST a natural language query and receive an answer grounded in documents I'm authorized to see with source citations,
So that I can get role-appropriate answers without manual document searching.

## Solution Statement

Implement in dependency order:

1. `pinecone_client.py` — lazy vectorstore factory + filtered retriever helper (k=10)
2. `rag_service.py` — LCEL chain: embed query → retrieve (k=10, RBAC filter) → rerank (top 3) → generate (Groq) → parse sources; wrapped with `@traceable`
3. `chat/router.py` — thin HTTP layer using `get_current_user` dependency
4. Update `main.py` — mount chat router + set Langsmith env vars from settings

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `backend/app/vector_store/`, `backend/app/chat/`, `backend/app/main.py`
**Dependencies**: langchain-groq, langchain-pinecone, langchain-google-genai, langsmith, pinecone>=7.3.0

---

## CONTEXT REFERENCES

### Already Implemented — Do NOT Modify

- `backend/app/config.py` — `settings` singleton with all API keys
- `backend/app/rbac/permissions.py` — `get_allowed_departments(role) -> list[str]`
- `backend/app/auth/service.py` — `get_current_user` dependency returns `{"username": str, "role": str}`
- `backend/app/main.py` — FastAPI app with CORS, auth router already mounted

### Verified API Signatures

```python
# Embedding — confirmed working
from langchain_google_genai import GoogleGenerativeAIEmbeddings
GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2-preview",
    google_api_key=str,
    output_dimensionality=768,
)

# Groq LLM
from langchain_groq import ChatGroq
ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=str)

# Pinecone vectorstore + RBAC-filtered retriever (k=10)
from langchain_pinecone import PineconeVectorStore
vectorstore.as_retriever(search_kwargs={"k": 10, "filter": {"department": {"$in": list}}})

# Pinecone native reranking
from pinecone import Pinecone
pc = Pinecone(api_key=str)
result = pc.inference.rerank(
    model="bge-reranker-v2-m3",
    query=str,
    documents=[str, ...],
    top_n=3,
    return_documents=False,
)
# result.data[i].index — original list index of reranked doc

# Langsmith tracing
from langsmith import traceable
@traceable
```

### Metadata Shape on Pinecone Chunks (from Phase 2)

```python
{
    "department": "finance",
    "source_file": "financial_summary.md",
    "section": "Q3 Summary",
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
  "sources": [{"file": "quarterly_financial_report.md", "section": "Q3 2024"}],
  "role": "finance"
}
```

### Langsmith Configuration Note

`pydantic-settings` loads `.env` into `settings` but does NOT update `os.environ`. LangChain reads tracing config from `os.environ`. Set these in `main.py` at startup:

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

EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
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


def get_retriever(allowed_departments: list[str], k: int = 10) -> VectorStoreRetriever:
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
- **GOTCHA**: `k=10` (not 5) — extra candidates needed for reranking in Task 2.
- **VALIDATE**: `cd backend && uv run python -c "from app.vector_store.pinecone_client import get_retriever; print('OK')"`

---

### TASK 2 — IMPLEMENT `backend/app/chat/rag_service.py`

```python
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langsmith import traceable
from pinecone import Pinecone

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


def _rerank(query: str, docs: list[Document], top_n: int = 3) -> list[Document]:
    """Rerank retrieved docs using Pinecone bge-reranker-v2-m3, return top_n."""
    if len(docs) <= top_n:
        return docs
    try:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        result = pc.inference.rerank(
            model="bge-reranker-v2-m3",
            query=query,
            documents=[doc.page_content for doc in docs],
            top_n=top_n,
            return_documents=False,
        )
        return [docs[item.index] for item in result.data]
    except Exception:
        return docs[:top_n]  # fallback: return first top_n unchanged


def _extract_sources(docs: list[Document]) -> list[dict]:
    """Deduplicate and extract source citations from retrieved documents."""
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

    # Retrieve k=10 candidates (RBAC filter applied server-side)
    retriever = get_retriever(allowed_depts)
    docs = retriever.invoke(query)

    if not docs:
        return {"answer": "I don't have access to that information.", "sources": [], "role": role}

    # Rerank to top 3 most relevant chunks
    docs = _rerank(query, docs, top_n=3)

    # Build context string from top 3 chunks
    context = "\n\n---\n\n".join(doc.page_content for doc in docs)

    chain = _prompt | _get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context, "question": query})

    return {"answer": answer, "sources": _extract_sources(docs), "role": role}
```

- **GOTCHA**: LCEL used instead of `RetrievalQAWithSourcesChain` — our metadata uses `source_file` not `source`.
- **GOTCHA**: `_rerank()` must be called AFTER the empty-docs check, not before.
- **GOTCHA**: `return_documents=False` — use `item.index` to map back to original `Document` objects.
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
    allow_origins=["http://localhost:3001"],   # Next.js frontend
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

- **GOTCHA**: CORS origin is `localhost:3001` (Next.js), not `localhost:3000` (old CRA).

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

### Level 3: Smoke test — reranking + source count

```bash
cd backend && uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from app.chat.rag_service import rag_query
r = rag_query('What is our gross margin?', 'finance')
print('Answer:', r['answer'][:100])
print('Sources:', len(r['sources']), r['sources'])
assert len(r['sources']) <= 3, 'Expected at most 3 sources after reranking'
print('RERANKING OK')
"
```

### Level 4: Full E2E regression

```bash
# Prerequisites: backend on :8000, frontend-next on :3001
bash test_e2e.sh
# Expect: 42/42 passed
```

---

## ACCEPTANCE CRITERIA

- [x] `POST /chat/query` as alice (finance) returns answer + sources from finance/general docs
- [x] `POST /chat/query` as frank (employee) asking about financials returns denial message
- [x] `POST /chat/query` without token returns 401
- [x] `sources` array contains at most 3 entries (post-rerank)
- [x] `role` field in response matches the authenticated user's role
- [x] Langsmith traces visible at smith.langchain.com
- [x] All 42 E2E regression tests pass

---

## NOTES

**Reranking strategy:** Retrieve k=10 by embedding similarity → rerank with `bge-reranker-v2-m3` cross-encoder → pass top 3 to LLM. Improved context_precision from 0.319 (k=5, no rerank) toward target ≥ 0.5. Fallback: `docs[:3]` if Pinecone inference API fails — pipeline never breaks.

**LCEL over RetrievalQAWithSourcesChain:** The PRD originally specified `RetrievalQAWithSourcesChain` but that requires a `source` metadata key. Our Pinecone chunks use `source_file` (Phase 2). LCEL is the modern LangChain 0.2+ approach and gives finer control over the pipeline.

**Lazy initialization:** `get_vectorstore()` and `_get_llm()` are called inside functions, not at module level. App starts cleanly even if API keys are temporarily missing.

**Groq model:** `llama-3.3-70b-versatile` replaces `llama-3.1-70b-versatile` (decommissioned by Groq, 2026-03-24).

**Embedding model:** `models/gemini-embedding-2-preview` with `output_dimensionality=768` replaces `text-embedding-004` (unavailable for this API key) and `gemini-embedding-001`.
