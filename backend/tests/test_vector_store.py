from unittest.mock import MagicMock, patch
from app.vector_store.pinecone_client import (
    _get_embeddings,
    get_vectorstore,
    get_retriever,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)


# ── _get_embeddings ────────────────────────────────────────────────────────────

def test_get_embeddings_uses_correct_model():
    with patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings") as mock_emb:
        _get_embeddings()
    mock_emb.assert_called_once()
    kwargs = mock_emb.call_args.kwargs
    assert kwargs["model"] == EMBEDDING_MODEL
    assert kwargs["output_dimensionality"] == EMBEDDING_DIMENSION


def test_get_embeddings_model_name_is_gemini_preview():
    assert EMBEDDING_MODEL == "models/gemini-embedding-2-preview"


def test_get_embeddings_dimension_is_768():
    assert EMBEDDING_DIMENSION == 768


# ── get_vectorstore ────────────────────────────────────────────────────────────

def test_get_vectorstore_passes_index_name():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        get_vectorstore()
    kwargs = mock_vs_cls.call_args.kwargs
    assert "index_name" in kwargs
    assert kwargs["index_name"] == "test"   # value set in conftest


def test_get_vectorstore_passes_api_key():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        get_vectorstore()
    kwargs = mock_vs_cls.call_args.kwargs
    assert "pinecone_api_key" in kwargs


def test_get_vectorstore_attaches_embeddings():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings") as mock_emb:
        mock_emb_instance = MagicMock()
        mock_emb.return_value = mock_emb_instance
        get_vectorstore()
    kwargs = mock_vs_cls.call_args.kwargs
    assert kwargs["embedding"] is mock_emb_instance


# ── get_retriever ──────────────────────────────────────────────────────────────

def test_get_retriever_rbac_filter_multi_dept():
    """Filter must pass all allowed departments as an $in list."""
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_vs_cls.return_value = mock_vs
        get_retriever(["finance", "general"], k=6)
    mock_vs.as_retriever.assert_called_once_with(
        search_kwargs={
            "k": 6,
            "filter": {"department": {"$in": ["finance", "general"]}},
        }
    )


def test_get_retriever_rbac_filter_single_dept():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_vs_cls.return_value = mock_vs
        get_retriever(["hr"], k=4)
    kwargs = mock_vs.as_retriever.call_args.kwargs
    assert kwargs["search_kwargs"]["filter"] == {"department": {"$in": ["hr"]}}
    assert kwargs["search_kwargs"]["k"] == 4


def test_get_retriever_rbac_filter_all_depts_c_level():
    """c_level gets all five departments in the filter."""
    all_depts = ["finance", "marketing", "hr", "engineering", "general"]
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_vs_cls.return_value = mock_vs
        get_retriever(all_depts, k=6)
    kwargs = mock_vs.as_retriever.call_args.kwargs
    assert set(kwargs["search_kwargs"]["filter"]["department"]["$in"]) == set(all_depts)


def test_get_retriever_k_parameter():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_vs_cls.return_value = mock_vs
        get_retriever(["general"], k=10)
    kwargs = mock_vs.as_retriever.call_args.kwargs
    assert kwargs["search_kwargs"]["k"] == 10


def test_get_retriever_returns_vectorstore_retriever():
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_retriever = MagicMock()
        mock_vs.as_retriever.return_value = mock_retriever
        mock_vs_cls.return_value = mock_vs
        result = get_retriever(["finance"], k=6)
    assert result is mock_retriever


def test_get_retriever_empty_departments():
    """Empty department list produces an empty $in filter."""
    with patch("app.vector_store.pinecone_client.PineconeVectorStore") as mock_vs_cls, \
         patch("app.vector_store.pinecone_client.GoogleGenerativeAIEmbeddings"):
        mock_vs = MagicMock()
        mock_vs_cls.return_value = mock_vs
        get_retriever([], k=6)
    kwargs = mock_vs.as_retriever.call_args.kwargs
    assert kwargs["search_kwargs"]["filter"] == {"department": {"$in": []}}
