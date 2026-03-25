# Feature: Phase 7 — Pinecone Native Reranking

**Status:** Complete ✅

## Feature Description

Add a cross-encoder reranking step between Pinecone retrieval and LLM generation to improve context precision. The pipeline retrieves k=10 candidate chunks by embedding similarity, then reranks them using Pinecone's `bge-reranker-v2-m3` model, passing only the top 3 most semantically relevant chunks to the LLM.

## User Story

As a developer,
I want retrieved chunks to be semantically reranked before reaching the LLM,
So that the model receives only the most relevant context and produces more accurate, focused answers.

## Problem Statement

Ragas evaluation showed `context_precision = 0.319` — roughly only 1.6 of the 5 retrieved chunks were genuinely relevant. Embedding similarity retrieval is fast but coarse; it ranks by vector proximity, not semantic relevance to the specific question.

## Solution Statement

Use Pinecone native reranking (`bge-reranker-v2-m3`) as a second-pass cross-encoder. Increase retrieval candidate pool to k=10, rerank to top 3. Zero new dependencies — Pinecone SDK already installed at v7.3.0.

## Feature Metadata

**Feature Type:** Enhancement to existing RAG pipeline
**Estimated Complexity:** Low
**Primary Systems Affected:** `backend/app/chat/rag_service.py`, `backend/app/vector_store/pinecone_client.py`, `backend/ingestion/evaluate.py`
**Dependencies:** `pinecone>=7.3.0` (already installed)

---

## Files Modified

| File | Change |
| --- | --- |
| `backend/app/vector_store/pinecone_client.py` | Default `k` changed from 5 → 10 |
| `backend/app/chat/rag_service.py` | Added `_rerank()` helper + reranking call in `rag_query()` |
| `backend/ingestion/evaluate.py` | Retrieval updated to k=10 + reranking for evaluation consistency |
| `test_e2e.sh` | RBAC test query updated to a marketing-specific KPI (ROAS) |

---

## Implementation Details

### `pinecone_client.py`

Changed default `k` from 5 to 10 so the reranker has a wider candidate pool:

```python
def get_retriever(allowed_departments: list[str], k: int = 10) -> VectorStoreRetriever:
```

### `rag_service.py`

Added `_rerank()` helper using `pc.inference.rerank()`:

```python
from pinecone import Pinecone

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
```

In `rag_query()`, inserted after the empty-docs check:

```python
docs = _rerank(query, docs, top_n=3)
```

### `evaluate.py`

Updated evaluation context retrieval to mirror production:

```python
from pinecone import Pinecone
from app.config import settings

retriever = get_retriever(allowed_depts, k=10)
docs = retriever.invoke(question)
if len(docs) > 3:
    try:
        _pc = Pinecone(api_key=settings.pinecone_api_key)
        reranked = _pc.inference.rerank(
            model="bge-reranker-v2-m3",
            query=question,
            documents=[d.page_content for d in docs],
            top_n=3,
            return_documents=False,
        )
        docs = [docs[item.index] for item in reranked.data]
    except Exception:
        docs = docs[:3]
context_texts = [doc.page_content for doc in docs]
```

### `test_e2e.sh` — RBAC query update

The "Finance cannot see marketing data" test used "What is the total marketing budget?" — a query that embedding similarity can partially answer from finance docs (which contain marketing expense line items). After reranking, the reranker surfaces those finance-doc chunks more aggressively.

Updated to a marketing-specific KPI that cannot appear in finance docs:

```bash
-d '{"query":"What was the Return on Ad Spend for digital campaigns?"}'
```

---

## Acceptance Criteria

- [x] `rag_query()` returns ≤ 3 sources per response
- [x] All 42 E2E regression tests pass
- [x] No errors when rerank API is called
- [x] Fallback works: if reranking fails, pipeline continues with `docs[:3]`
- [x] `evaluate.py` context retrieval uses reranking for consistent measurement

---

## Validation

```bash
# Smoke test — verify ≤ 3 sources returned
cd backend && uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from app.chat.rag_service import rag_query
r = rag_query('What is our gross margin?', 'finance')
print('Sources:', len(r['sources']), r['sources'])
"

# Full regression suite
bash test_e2e.sh
```

---

## Notes

- Pinecone `bge-reranker-v2-m3` is a hosted cross-encoder — no model weights downloaded locally
- `return_documents=False` saves bandwidth; index mapping (`item.index`) used to retrieve original `Document` objects
- Re-run Ragas evaluation after Groq quota resets to confirm context_precision improvement from 0.319 baseline
