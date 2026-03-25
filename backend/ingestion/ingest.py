"""
One-time ingestion script — populates Pinecone with all company documents.

WARNING: Re-running this script will create DUPLICATE vectors in Pinecone.
Run only once per fresh index. To re-ingest, delete the index manually in
the Pinecone console first, then run this script again.
"""
import os
import sys
import time
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

EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
EMBEDDING_DIMENSION = 768
BATCH_SIZE = 25
BATCH_SLEEP_SECONDS = 15  # free-tier rate limit: 100 req/min


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
        output_dimensionality=EMBEDDING_DIMENSION,
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
        if batch_num < total_batches:
            time.sleep(BATCH_SLEEP_SECONDS)

    print(f"\nIngestion complete — {len(chunks)} vectors upserted to '{PINECONE_INDEX_NAME}'.")


if __name__ == "__main__":
    run_ingestion()
