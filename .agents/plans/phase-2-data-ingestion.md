# Feature: Phase 2 — Data Ingestion Pipeline

The following plan should be complete, but validate all imports and API signatures against the installed packages before implementing. All packages are already installed in `backend/.venv`.

Pay special attention to metadata propagation through the LangChain splitter chain — `MarkdownHeaderTextSplitter` does NOT preserve parent document metadata (department, source_file). It must be re-injected manually on every chunk.

## Feature Description

Build the one-time ingestion pipeline that loads all 10 source documents, chunks them with heading-aware splitting and size limits, embeds them with Google `text-embedding-004`, and upserts them into a Pinecone serverless index with full RBAC metadata attached. This pipeline runs once to populate the vector database; downstream RAG queries in Phase 4 rely entirely on the metadata schema defined here.

## User Story

As a developer,
I want to run `uv run python -m ingestion.ingest` once and have all documents loaded into Pinecone,
So that the Phase 4 RAG service can perform RBAC-filtered vector searches against properly tagged chunks.

## Problem Statement

All three ingestion files (`loaders.py`, `chunker.py`, `ingest.py`) are empty stubs. No documents are indexed. The Phase 4 RAG service cannot function until vectors with correct `department` metadata are present in Pinecone.

## Solution Statement

Implement the three ingestion modules in dependency order:
1. `loaders.py` — loads raw documents from `resources/data/`, tags each with `{department, source_file, doc_type}`
2. `chunker.py` — splits markdown by headers then size; CSV rows are already atomic; attaches `chunk_id`
3. `ingest.py` — orchestrates load → chunk → embed → upsert with batching

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `backend/ingestion/`
**Dependencies**: All installed — langchain 1.2.13, pinecone 7.3.0, langchain-google-genai, langchain-pinecone, pandas 2.3.3

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `CLAUDE.md` — RBAC Access Matrix table (department names must match exactly: `finance`, `marketing`, `hr`, `engineering`, `general`)
- `PRD.md` §4 Feature 4 (lines 201–206) — chunking spec: `MarkdownHeaderTextSplitter` on `##`/`###`, then `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)`, CSV row-per-doc, metadata shape `{department, source_file, doc_type, chunk_id}`
- `PRD.md` §15 Appendix (Source Documents table) — canonical list of all 10 files with their department assignments
- `backend/.env.example` — env var names: `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GOOGLE_API_KEY`

### Source Documents (DO NOT MODIFY)

```
resources/data/
├── finance/        financial_summary.md, quarterly_financial_report.md      → department: "finance"
├── marketing/      5 × marketing report .md files                           → department: "marketing"
├── engineering/    engineering_master_doc.md (756 lines)                    → department: "engineering"
├── general/        employee_handbook.md (352 lines)                         → department: "general"
└── hr/             hr_data.csv (100 data rows, 1 header row)                → department: "hr"
```

### New Files to Implement

- `backend/ingestion/loaders.py` — raw document loading + department tagging
- `backend/ingestion/chunker.py` — splitting + metadata enrichment
- `backend/ingestion/ingest.py` — end-to-end pipeline entry point

### Relevant Documentation — READ BEFORE IMPLEMENTING

- [MarkdownHeaderTextSplitter](https://python.langchain.com/docs/how_to/markdown_header_metadata_splitter/)
  - Section: Headers-to-split-on format, metadata output
  - Why: Confirmed API — `headers_to_split_on=[("##", "section"), ("###", "subsection")]`; output chunks only carry header metadata — NOT parent doc metadata. Must re-inject manually.
- [RecursiveCharacterTextSplitter](https://python.langchain.com/docs/how_to/recursive_text_splitter/)
  - Why: Second-pass size splitter; preserves whatever metadata the input Document has
- [PineconeVectorStore (langchain-pinecone)](https://python.langchain.com/docs/integrations/vectorstores/pinecone/)
  - Why: `PineconeVectorStore(index_name=..., embedding=..., pinecone_api_key=...)` then `.add_documents(batch)` for batch upsert
- [Pinecone Python SDK v7 — create_index](https://docs.pinecone.io/reference/api/control-plane/create_index)
  - Why: `pc.create_index(name, spec=ServerlessSpec(cloud="aws", region="us-east-1"), dimension=768, metric="cosine")` — `spec` is required in v7
- [GoogleGenerativeAIEmbeddings](https://python.langchain.com/docs/integrations/text_embedding/google_generative_ai/)
  - Why: `GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=...)` — note `models/` prefix

### Verified API Signatures (from installed packages)

```python
# Confirmed working imports
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
import pandas as pd

# MarkdownHeaderTextSplitter — confirmed output metadata keys
splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "section"), ("###", "subsection")])
# chunk.metadata = {"section": "Heading Text"} or {"section": "...", "subsection": "..."}
# GOTCHA: parent doc metadata (department, source_file) is NOT present in output chunks

# Pinecone v7 list_indexes — use .names() method
pc = Pinecone(api_key=PINECONE_API_KEY)
existing_names: list[str] = pc.list_indexes().names()

# Pinecone v7 create_index signature
pc.create_index(
    name=index_name,
    dimension=768,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)

# PineconeVectorStore — init then add_documents for batching
vectorstore = PineconeVectorStore(
    index_name=PINECONE_INDEX_NAME,
    embedding=embeddings,
    pinecone_api_key=PINECONE_API_KEY,
)
vectorstore.add_documents(batch)  # batch is list[Document]
```

### Patterns to Follow

**Import style** (Python, snake_case files, PascalCase classes — from CLAUDE.md):
```python
from pathlib import Path
from langchain_core.documents import Document
```

**Metadata shape** (canonical — every chunk must have all 4 keys):
```python
{
    "department": "finance",          # one of: finance, marketing, hr, engineering, general
    "source_file": "financial_summary.md",  # basename only, no path
    "doc_type": "markdown",           # "markdown" or "csv"
    "chunk_id": "financial_summary_0",# {stem}_{index}
}
```

**chunk_id format**: `f"{Path(source_file).stem}_{i}"` — stem of filename + zero-based index within that file's chunks.

**CSV row format** — sentence-like string that embeds semantically:
```python
content = ". ".join(f"{col}: {val}" for col, val in row.items())
```
This produces: `"employee_id: FINEMP1000. full_name: Aadhya Patel. role: Sales Manager. ..."` — readable for the LLM and meaningful for embeddings.

**DATA_DIR path** — always resolve relative to the file, not cwd (ingest.py runs from `backend/`):
```python
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "data"
```

---

## IMPLEMENTATION PLAN

### Phase 2A: loaders.py
Load raw documents, tag metadata. No chunking here — just raw content + `{department, source_file, doc_type}`.

### Phase 2B: chunker.py
Split and enrich. Markdown: header split → size split → re-inject parent metadata + chunk_id. CSV: already atomic rows, just add chunk_id.

### Phase 2C: ingest.py
Orchestrate everything: load → chunk → create Pinecone index if absent → init embeddings → batch upsert.

---

## STEP-BY-STEP TASKS

### TASK 1 — IMPLEMENT `backend/ingestion/loaders.py`

**Full implementation:**

```python
from pathlib import Path
from langchain_core.documents import Document
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "data"

DEPARTMENT_DIRS: dict[str, Path] = {
    "finance": DATA_DIR / "finance",
    "marketing": DATA_DIR / "marketing",
    "hr": DATA_DIR / "hr",
    "engineering": DATA_DIR / "engineering",
    "general": DATA_DIR / "general",
}


def load_markdown_documents() -> list[Document]:
    """Load all .md files from all department directories."""
    docs: list[Document] = []
    for dept, dir_path in DEPARTMENT_DIRS.items():
        for md_file in sorted(dir_path.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            docs.append(Document(
                page_content=content,
                metadata={
                    "department": dept,
                    "source_file": md_file.name,
                    "doc_type": "markdown",
                },
            ))
    return docs


def load_csv_documents() -> list[Document]:
    """Load all .csv files — each row becomes one Document."""
    docs: list[Document] = []
    for dept, dir_path in DEPARTMENT_DIRS.items():
        for csv_file in sorted(dir_path.glob("*.csv")):
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                content = ". ".join(f"{col}: {val}" for col, val in row.items())
                docs.append(Document(
                    page_content=content,
                    metadata={
                        "department": dept,
                        "source_file": csv_file.name,
                        "doc_type": "csv",
                    },
                ))
    return docs


def load_all_documents() -> list[Document]:
    """Load all markdown and CSV documents from all departments."""
    return load_markdown_documents() + load_csv_documents()
```

- **GOTCHA**: `DATA_DIR` uses `Path(__file__).resolve().parent.parent.parent` — `loaders.py` is in `backend/ingestion/`, so 3 parents up reaches the repo root, then `/resources/data`. Verify this path is correct before running.
- **GOTCHA**: `sorted()` on glob results ensures deterministic ordering across OS platforms.
- **VALIDATE**:
```bash
cd backend && uv run python -c "
from ingestion.loaders import load_all_documents
docs = load_all_documents()
print(f'Total docs: {len(docs)}')
depts = {}
for d in docs:
    depts[d.metadata['department']] = depts.get(d.metadata['department'], 0) + 1
print(depts)
"
```
Expected: `Total docs: 110` (9 MD files + 100 CSV rows + 1 header skipped = actually 109 docs: 9 MD + 100 CSV rows). Finance=2, marketing=5, engineering=1, general=1, hr=100.

---

### TASK 2 — IMPLEMENT `backend/ingestion/chunker.py`

**Full implementation:**

```python
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pathlib import Path

HEADERS_TO_SPLIT_ON = [("##", "section"), ("###", "subsection")]
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON)
_text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


def _chunk_markdown(doc: Document) -> list[Document]:
    """Split a markdown Document by headers then by size. Re-injects parent metadata."""
    header_chunks = _header_splitter.split_text(doc.page_content)
    size_chunks = _text_splitter.split_documents(header_chunks)

    stem = Path(doc.metadata["source_file"]).stem
    result: list[Document] = []
    for i, chunk in enumerate(size_chunks):
        result.append(Document(
            page_content=chunk.page_content,
            metadata={
                "department": doc.metadata["department"],
                "source_file": doc.metadata["source_file"],
                "doc_type": "markdown",
                "section": chunk.metadata.get("section", ""),
                "subsection": chunk.metadata.get("subsection", ""),
                "chunk_id": f"{stem}_{i}",
            },
        ))
    return result


def _chunk_csv_row(doc: Document, index: int) -> Document:
    """CSV rows are already atomic — just attach chunk_id."""
    stem = Path(doc.metadata["source_file"]).stem
    return Document(
        page_content=doc.page_content,
        metadata={
            "department": doc.metadata["department"],
            "source_file": doc.metadata["source_file"],
            "doc_type": "csv",
            "section": "",
            "subsection": "",
            "chunk_id": f"{stem}_{index}",
        },
    )


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Chunk all documents. Markdown: header+size split. CSV: passthrough with chunk_id."""
    chunked: list[Document] = []
    csv_counters: dict[str, int] = {}

    for doc in docs:
        if doc.metadata.get("doc_type") == "markdown":
            chunked.extend(_chunk_markdown(doc))
        elif doc.metadata.get("doc_type") == "csv":
            source = doc.metadata["source_file"]
            idx = csv_counters.get(source, 0)
            chunked.append(_chunk_csv_row(doc, idx))
            csv_counters[source] = idx + 1

    return chunked
```

- **GOTCHA**: `MarkdownHeaderTextSplitter.split_text()` takes a `str`, not a `Document`. Use `doc.page_content`.
- **GOTCHA**: `RecursiveCharacterTextSplitter.split_documents()` takes `list[Document]` and preserves the metadata already on those Documents (the header metadata). That's why `section`/`subsection` is available via `chunk.metadata.get(...)` after size-splitting.
- **GOTCHA**: A markdown doc with no `##` or `###` headers at all will produce a single chunk — `_header_splitter` returns `[Document(page_content=full_text, metadata={})]`. The `_chunk_markdown` function handles this — `section`/`subsection` will be empty strings.
- **VALIDATE**:
```bash
cd backend && uv run python -c "
from ingestion.loaders import load_all_documents
from ingestion.chunker import chunk_documents
docs = load_all_documents()
chunks = chunk_documents(docs)
print(f'Total chunks: {len(chunks)}')
# Spot check metadata completeness
sample = chunks[0]
required = {'department','source_file','doc_type','chunk_id'}
assert required.issubset(sample.metadata.keys()), f'Missing keys: {required - sample.metadata.keys()}'
# Verify all chunks have department set
assert all(c.metadata.get('department') for c in chunks), 'Some chunks missing department'
print('All metadata checks passed')
print('Sample:', chunks[0].metadata)
"
```

---

### TASK 3 — IMPLEMENT `backend/ingestion/ingest.py`

**Full implementation:**

```python
"""
One-time ingestion script — populates Pinecone with all company documents.

WARNING: Re-running this script will create DUPLICATE vectors in Pinecone.
Run only once per fresh index. To re-ingest, delete the index manually in
the Pinecone console first, then run this script again.
"""
import os
import sys
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from ingestion.loaders import load_all_documents
from ingestion.chunker import chunk_documents

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "rag-rbac-chatbot")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSION = 768
BATCH_SIZE = 100


def _validate_env() -> None:
    missing = [v for v in ["PINECONE_API_KEY", "PINECONE_INDEX_NAME", "GOOGLE_API_KEY"] if not os.getenv(v)]
    if missing:
        print(f"ERROR: Missing environment variables: {missing}")
        print("Copy backend/.env.example to backend/.env and fill in real keys.")
        sys.exit(1)


def _create_index_if_absent(pc: Pinecone) -> None:
    existing = pc.list_indexes().names()
    if PINECONE_INDEX_NAME in existing:
        print(f"Index '{PINECONE_INDEX_NAME}' already exists — skipping creation.")
        return
    print(f"Creating Pinecone index '{PINECONE_INDEX_NAME}' (dim={EMBEDDING_DIMENSION}, cosine)...")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    print("Index created.")


def run_ingestion() -> None:
    _validate_env()

    # 1. Load raw documents
    print("\n[1/4] Loading documents...")
    docs = load_all_documents()
    print(f"  Loaded {len(docs)} raw documents")

    # 2. Chunk
    print("\n[2/4] Chunking documents...")
    chunks = chunk_documents(docs)
    print(f"  Created {len(chunks)} chunks")

    # 3. Init Pinecone and create index if needed
    print("\n[3/4] Initialising Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    _create_index_if_absent(pc)

    # 4. Embed and upsert in batches
    print(f"\n[4/4] Embedding and upserting {len(chunks)} chunks (batch size={BATCH_SIZE})...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
    vectorstore = PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=embeddings,
        pinecone_api_key=PINECONE_API_KEY,
    )

    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        vectorstore.add_documents(batch)
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} done ({len(batch)} chunks)")

    print(f"\nIngestion complete — {len(chunks)} vectors upserted to '{PINECONE_INDEX_NAME}'.")


if __name__ == "__main__":
    run_ingestion()
```

- **GOTCHA**: `load_dotenv()` must be called before reading `os.getenv()`. Already handled at module top.
- **GOTCHA**: `ServerlessSpec(cloud="aws", region="us-east-1")` is the standard free-tier region. If the user's Pinecone account is in a different region (e.g., `gcp-starter`), they will need to adjust. Document this in the warning comment.
- **GOTCHA**: `PineconeVectorStore.add_documents()` calls the Google embedding API for each batch. The Google `text-embedding-004` API has rate limits — if 429 errors occur, reduce `BATCH_SIZE` to 25 or add retry logic with `time.sleep(2)` between batches.
- **GOTCHA**: The script is NOT idempotent — re-running adds duplicates. The WARNING docstring and `_create_index_if_absent` (which skips creation but still upserts) make this clear.
- **VALIDATE**:
```bash
cd backend && uv run python -c "
from ingestion.ingest import run_ingestion
# Dry-run import check only (no .env needed for this)
print('ingest.py imports OK')
"
```

---

### TASK 4 — END-TO-END DRY RUN (no API keys needed)

Verify the full pipeline from load → chunk with real data, without hitting any external APIs:

```bash
cd backend && uv run python -c "
from ingestion.loaders import load_all_documents
from ingestion.chunker import chunk_documents
from collections import Counter

docs = load_all_documents()
chunks = chunk_documents(docs)

# Dept distribution
dept_counts = Counter(c.metadata['department'] for c in chunks)
print('Chunks by department:', dict(dept_counts))

# Doc type distribution
type_counts = Counter(c.metadata['doc_type'] for c in chunks)
print('Chunks by doc_type:', dict(type_counts))

# Verify all required metadata fields
required = {'department', 'source_file', 'doc_type', 'chunk_id'}
bad = [c for c in chunks if not required.issubset(c.metadata.keys())]
print(f'Chunks missing required metadata: {len(bad)}')

# Verify chunk_ids are unique
ids = [c.metadata['chunk_id'] for c in chunks]
print(f'Unique chunk_ids: {len(set(ids))} / {len(ids)}')

# Verify no empty page_content
empty = [c for c in chunks if not c.page_content.strip()]
print(f'Chunks with empty content: {len(empty)}')

print('DRY RUN COMPLETE')
"
```

Expected:
- All 5 departments represented
- csv doc_type count = 100 (one per hr_data row)
- 0 chunks missing required metadata
- All chunk_ids unique
- 0 empty content chunks

---

### TASK 5 — RUN LIVE INGESTION (requires `.env`)

Only run after `.env` is populated with real API keys:

```bash
cd backend && uv run python -m ingestion.ingest
```

Expected output sequence:
```
[1/4] Loading documents...
  Loaded 109 raw documents
[2/4] Chunking documents...
  Created ~N chunks
[3/4] Initialising Pinecone...
  Creating Pinecone index 'rag-rbac-chatbot' (dim=768, cosine)...
  Index created.
[4/4] Embedding and upserting N chunks (batch size=100)...
  Batch 1/M done (100 chunks)
  ...
Ingestion complete — N vectors upserted to 'rag-rbac-chatbot'.
```

---

## TESTING STRATEGY

### Unit Tests (No API keys required)

All dry-run validation from Tasks 1–4 qualifies as unit-level testing. No test framework is set up in Phase 2 — validation is via the inline `uv run python -c` commands above.

### Integration Tests (API keys required)

After live ingestion (Task 5), verify with a direct Pinecone filtered query:

```bash
cd backend && uv run python -c "
import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index(os.getenv('PINECONE_INDEX_NAME', 'rag-rbac-chatbot'))

embeddings = GoogleGenerativeAIEmbeddings(
    model='models/text-embedding-004',
    google_api_key=os.getenv('GOOGLE_API_KEY'),
)
query_vec = embeddings.embed_query('What is the gross margin?')

# Finance-only filter
result = index.query(
    vector=query_vec,
    top_k=3,
    filter={'department': {'\\$in': ['finance']}},
    include_metadata=True,
)
print('Finance results:')
for match in result['matches']:
    print(f'  score={match[\"score\"]:.3f} dept={match[\"metadata\"][\"department\"]} file={match[\"metadata\"][\"source_file\"]}')

# General-only filter
result2 = index.query(
    vector=query_vec,
    top_k=3,
    filter={'department': {'\\$in': ['general']}},
    include_metadata=True,
)
print('General results:')
for match in result2['matches']:
    print(f'  score={match[\"score\"]:.3f} dept={match[\"metadata\"][\"department\"]} file={match[\"metadata\"][\"source_file\"]}')
"
```

Expected: Finance results all have `department=finance`; general results all have `department=general`. No cross-department leakage.

### Edge Cases

- **Markdown with no headers**: `_header_splitter` returns a single chunk with empty metadata — `section`/`subsection` become `""`. Handled by `.get("section", "")`.
- **Markdown smaller than chunk_size**: `_text_splitter` returns a single chunk — fine.
- **CSV with NaN values**: `pandas` may produce `float('nan')` for missing cells. `f"{col}: {val}"` will render as `"col: nan"`. Acceptable for MVP.
- **Duplicate chunk_ids across files**: `chunk_id = f"{stem}_{i}"` is per-file, so `financial_summary_0` and `quarterly_financial_report_0` are distinct. Within a file, the index `i` is sequential. Unique across all chunks — confirmed by Task 4 dry-run assertion.

---

## VALIDATION COMMANDS

### Level 1: Import check

```bash
cd backend && uv run python -c "
from ingestion.loaders import load_all_documents
from ingestion.chunker import chunk_documents
from ingestion.ingest import run_ingestion
print('ALL IMPORTS OK')
"
```

### Level 2: Dry-run pipeline (full Task 4 command)

```bash
cd backend && uv run python -c "
from ingestion.loaders import load_all_documents
from ingestion.chunker import chunk_documents
from collections import Counter
docs = load_all_documents()
chunks = chunk_documents(docs)
dept_counts = Counter(c.metadata['department'] for c in chunks)
required = {'department','source_file','doc_type','chunk_id'}
bad = [c for c in chunks if not required.issubset(c.metadata.keys())]
ids = [c.metadata['chunk_id'] for c in chunks]
empty = [c for c in chunks if not c.page_content.strip()]
assert len(bad) == 0, f'{len(bad)} chunks missing metadata'
assert len(set(ids)) == len(ids), f'Duplicate chunk_ids: {len(ids)-len(set(ids))}'
assert len(empty) == 0, f'{len(empty)} empty chunks'
print('dept distribution:', dict(dept_counts))
print('VALIDATION PASSED')
"
```

### Level 3: Live ingestion (requires `.env`)

```bash
cd backend && uv run python -m ingestion.ingest
```

### Level 4: Post-ingestion Pinecone filter test (requires `.env`)

Run the integration test query from the Testing Strategy section above. Verify all results respect the department filter.

---

## ACCEPTANCE CRITERIA

- [ ] `loaders.py`: `load_all_documents()` returns Documents for all 10 source files (9 MD + 1 CSV × 100 rows = 109 documents)
- [ ] `loaders.py`: Every Document has `{department, source_file, doc_type}` in metadata
- [ ] `loaders.py`: Department values are exactly one of: `finance`, `marketing`, `hr`, `engineering`, `general`
- [ ] `chunker.py`: `chunk_documents()` produces chunks with all 4 required metadata keys: `{department, source_file, doc_type, chunk_id}`
- [ ] `chunker.py`: All chunk_ids are unique (no duplicates)
- [ ] `chunker.py`: No chunks with empty `page_content`
- [ ] `chunker.py`: CSV rows are not further split (100 CSV rows → 100 CSV chunks)
- [ ] `ingest.py`: Validates missing env vars and exits cleanly with helpful message
- [ ] `ingest.py`: Does not create a duplicate Pinecone index if one already exists
- [ ] `ingest.py`: Imports cleanly with no API calls when `.env` is absent
- [ ] Live ingestion: Pinecone index contains vectors with correct `department` metadata
- [ ] Live ingestion: Filtered query `{department: {$in: ["finance"]}}` returns only finance chunks
- [ ] All Level 1 and Level 2 validation commands pass with zero errors

---

## COMPLETION CHECKLIST

- [ ] Task 1 (loaders.py) implemented and Level 1 validate passes
- [ ] Task 2 (chunker.py) implemented and per-task validate passes
- [ ] Task 3 (ingest.py) implemented and import check passes
- [ ] Task 4 dry-run passes: 0 bad metadata, 0 duplicate IDs, 0 empty chunks
- [ ] Task 5 live ingestion run (if `.env` is populated)
- [ ] Level 2 full dry-run validation command passes
- [ ] Level 4 Pinecone filter test passes (if live)
- [ ] All acceptance criteria checked off

---

## NOTES

**`DATA_DIR` path resolution**: `Path(__file__).resolve()` in `loaders.py` gives the absolute path of `loaders.py` itself (`backend/ingestion/loaders.py`). Three `.parent` calls: `ingestion/ → backend/ → rag_project/`. Then `/ "resources" / "data"` = `rag_project/resources/data`. This is correct regardless of where `uv run` is invoked from.

**Pinecone region**: `ServerlessSpec(cloud="aws", region="us-east-1")` is the free-tier default. Users on GCP-based or EU Pinecone accounts must change this. If index creation fails with a region error, check the Pinecone console for the correct cloud/region.

**Google embedding rate limits**: `text-embedding-004` has a requests-per-minute limit on free API keys. If 429 errors occur during upsert, reduce `BATCH_SIZE` from 100 to 25 and add `import time; time.sleep(2)` after each `vectorstore.add_documents(batch)` call.

**Re-ingestion guard**: The script does NOT prevent re-running — `_create_index_if_absent` skips index creation but still upserts. To safely re-ingest, delete the Pinecone index via the console, then run the script again. Do not add an auto-delete to the script — deletion is irreversible.

**Metadata in Phase 4**: The `department` key in Pinecone metadata is what Phase 4's `pinecone_client.py` filters on. The exact string values (`"finance"`, `"hr"`, etc.) must match `get_allowed_departments()` output in `rbac/permissions.py` (implemented in Phase 3). The values defined here are the canonical source.

**`section` and `subsection` metadata**: These are optional convenience fields (populated from markdown headers). Phase 4's source citations use `source_file` as the primary citation. `section`/`subsection` can be surfaced as finer-grained citation context in the response.
