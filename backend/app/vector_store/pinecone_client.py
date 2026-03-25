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


def get_retriever(allowed_departments: list[str], k: int = 5) -> VectorStoreRetriever:
    """Return a Pinecone retriever pre-filtered to the given departments."""
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(
        search_kwargs={
            "k": k,
            "filter": {"department": {"$in": allowed_departments}},
        }
    )
