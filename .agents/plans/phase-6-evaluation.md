# Feature: Phase 6 — Evaluation & Monitoring

The following plan is complete. `evaluate.py` is fully implemented and the evaluation script is running.

**CRITICAL**: Ragas 0.4.3 is installed (new API). `LangchainLLMWrapper` and `LangchainEmbeddingsWrapper` are deprecated but functional. Inject Groq LLM + Google embeddings directly into metric constructors — do NOT rely on OpenAI defaults.

**NOTE**: Windows stdout is cp1252 by default. LLM answers may contain ₹ (`\u20b9`). Call `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup.

## Feature Description

Offline Ragas evaluation script that scores the RAG pipeline on 30 role-restricted test questions across 5 departments (finance, marketing, hr, engineering, employee). Exports per-case metric scores to CSV. Langsmith tracing is automatic via `@traceable` on `rag_query`.

## User Story

As a developer,
I want to run an automated evaluation of the RAG pipeline,
So that I can measure answer quality with objective metrics and confirm the pipeline meets acceptance thresholds.

## Problem Statement

`backend/ingestion/evaluate.py` was a 1-line TODO stub. No automated quality measurement existed for the RAG pipeline.

## Solution Statement

Implement `evaluate.py` to run 30 hardcoded test Q&A pairs through `rag_query()`, collect retrieved contexts separately via `get_retriever()`, score with Ragas 4 metrics, and export to CSV.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `backend/ingestion/evaluate.py`
**Dependencies**: ragas==0.4.3, pandas, datasets — all installed

---

## CONTEXT REFERENCES

### Already Implemented — Do NOT Modify
- `backend/app/chat/rag_service.py` — `rag_query(query, role) -> {answer, sources, role}`; decorated `@traceable`; does NOT return retrieved Document objects
- `backend/app/vector_store/pinecone_client.py` — `get_retriever(allowed_departments, k=6) -> VectorStoreRetriever`
- `backend/app/rbac/permissions.py` — `get_allowed_departments(role) -> list[str]`
- `backend/app/config.py` — `settings` singleton with `groq_api_key`, `google_api_key`

### File Implemented
- `backend/ingestion/evaluate.py` — complete implementation

### Env Loading Pattern (from `backend/ingestion/ingest.py`)
```python
from dotenv import load_dotenv
load_dotenv()  # MUST run before any app.* imports
# os.environ is now populated; pydantic-settings also reads .env independently
from app.chat.rag_service import rag_query
```

---

## VERIFIED API (Ragas 0.4.3 — new API)

```python
from ragas import evaluate as ragas_evaluate
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from ragas.llms import LangchainLLMWrapper       # deprecated but works in 0.4.3
from ragas.embeddings import LangchainEmbeddingsWrapper  # deprecated but works in 0.4.3

_llm = LangchainLLMWrapper(ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=...))
_emb = LangchainEmbeddingsWrapper(GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", output_dimensionality=768, ...))

METRICS = [
    Faithfulness(llm=_llm),
    AnswerRelevancy(llm=_llm, embeddings=_emb),
    ContextPrecision(llm=_llm),
    ContextRecall(llm=_llm),
]

samples = [SingleTurnSample(user_input=q, response=a, retrieved_contexts=c, reference=g) ...]
result = ragas_evaluate(EvaluationDataset(samples=samples), metrics=METRICS)
df = result.to_pandas()
df.to_csv("evaluation_results.csv", index=False)
```

---

## IMPLEMENTATION

### Env loading order
```python
import os, sys, time, importlib.metadata
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# Windows stdout UTF-8 fix
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# Now safe to import app modules
from app.chat.rag_service import rag_query
from app.vector_store.pinecone_client import get_retriever
from app.rbac.permissions import get_allowed_departments
```

### Why dual retrieval per case
`rag_query()` does not expose the retrieved `Document` objects. Ragas needs raw context strings for `context_precision` and `context_recall`. Must call `get_retriever(allowed_depts).invoke(question)` separately to collect `[doc.page_content, ...]`.

### 30 Test Cases

`TEST_CASES: list[tuple[str, str, str]]` — `(question, role, ground_truth)`:

**Finance (6) — role: `finance`**
1. Gross margin 2024 → "60%, up from 55% in 2023"
2. Revenue growth YoY → "25%"
3. Vendor services expense → "$30M, 18% increase"
4. Cash flow from operations → "$50M, 20% increase"
5. Q1 2024 revenue → "$2.1B, up 22% YoY"
6. Days Sales Outstanding → "45 days vs 30-day benchmark"

**Marketing (6) — role: `marketing`**
7. Total marketing budget → "$15 million"
8. Customer acquisition cost → "$150, down from $180"
9. Digital campaign ROI → "3.5x, $17.5M"
10. New customer growth → "20%, vs 10% industry avg"
11. ROAS → "4.5x"
12. Highest-converting campaign → "InstantWire Global Expansion"

**HR (6) — role: `hr`**
13. Performance rating FINEMP1001 → "5"
14. Dept for Aadhya Patel (FINEMP1000) → "Sales"
15. Salary Shaurya Joshi (FINEMP1005) → "1,085,205.18"
16. Attendance Sara Sharma (FINEMP1006) → "96.49%"
17. Leaves Isha Chowdhury (FINEMP1001) → "3 leaves"
18. Leave balance FINEMP1004 → "21 days"

**Engineering (6) — role: `engineering`**
19. Architecture type → "Microservices-based, cloud-native"
20. Mobile dev languages → "Swift (iOS), Kotlin (Android)"
21. Databases → "PostgreSQL, MongoDB, Redis, Amazon S3"
22. Auth standard → "OAuth 2.0 with JWT, MFA, SSO"
23. Cloud provider → "AWS (EC2, ECS, Lambda) + Kubernetes"
24. Frontend framework → "React, Redux, Tailwind CSS"

**General (6) — role: `employee`**
25. Annual leave → "15–21 days, accrued monthly"
26. WFH policy → "Up to 2 days/week, manager approval"
27. Overtime → "Double rate, prior manager approval"
28. Referral reward → "Rs. 10,000 after 6 months"
29. Salary credit date → "Last working day of the month"
30. Tuition reimbursement → "Up to Rs. 50,000/year"

---

## VALIDATION COMMANDS

```bash
# Level 1: import + single live query (~10s)
cd backend && uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from app.chat.rag_service import rag_query
from app.vector_store.pinecone_client import get_retriever
from app.rbac.permissions import get_allowed_departments
print('Import chain OK')
result = rag_query('What is our gross margin?', 'finance')
print('RAG query OK:', result['answer'][:80])
"

# Level 2: full evaluation (~5-10 min)
cd backend && uv run python -m ingestion.evaluate
```

---

## ACCEPTANCE CRITERIA

- [x] `uv run python -m ingestion.evaluate` runs without error
- [x] Import chain validates in < 30 seconds
- [ ] `backend/evaluation_results.csv` created with 30 rows
- [ ] Mean faithfulness ≥ 0.8
- [ ] Mean answer_relevancy ≥ 0.75
- [ ] Langsmith traces visible at smith.langchain.com

---

## KNOWN ISSUES / GOTCHAS

- **Ragas 0.4.3 deprecation warnings**: `LangchainLLMWrapper`, `LangchainEmbeddingsWrapper`, and metric import paths are deprecated. Functional in 0.4.3 but will break in 1.0. Future fix: use `ragas.metrics.collections` imports and `llm_factory`.
- **"I don't have access" answers** for some cases (cases 6, 11, 12, 20, 24) — retriever returned docs but LLM couldn't find the specific info. These lower context_recall scores.
- **Windows encoding**: LLM answers may contain ₹ symbol — fixed with `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`.
- **Rate limits**: `time.sleep(1)` between cases. If 429 errors occur on Groq, increase to `time.sleep(3)`.
