from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from app.chat.rag_service import _extract_sources, _rerank, rag_query


def _doc(file="file.md", section="Section"):
    d = Document(page_content="content")
    d.metadata = {"source_file": file, "section": section}
    return d


def test_extract_sources_deduplicates():
    docs = [_doc("a.md", "S1"), _doc("a.md", "S1")]
    assert _extract_sources(docs) == [{"file": "a.md", "section": "S1"}]


def test_extract_sources_different_sections():
    docs = [_doc("a.md", "S1"), _doc("a.md", "S2")]
    assert len(_extract_sources(docs)) == 2


def test_extract_sources_empty():
    assert _extract_sources([]) == []


def test_extract_sources_missing_metadata():
    d = Document(page_content="content")
    d.metadata = {}
    result = _extract_sources([d])
    assert result == [{"file": "", "section": ""}]


def test_extract_sources_preserves_order():
    docs = [_doc("b.md", "S1"), _doc("a.md", "S1")]
    result = _extract_sources(docs)
    assert result[0]["file"] == "b.md"
    assert result[1]["file"] == "a.md"


def test_rerank_no_call_when_docs_le_top_n():
    docs = [_doc() for _ in range(3)]
    with patch("app.chat.rag_service.Pinecone") as mock_pc:
        result = _rerank("query", docs, top_n=3)
        mock_pc.assert_not_called()
    assert result == docs


def test_rerank_returns_top_n():
    docs = [_doc(f"file{i}.md", f"S{i}") for i in range(5)]
    mock_item = lambda i: MagicMock(index=i)
    mock_result = MagicMock()
    mock_result.data = [mock_item(2), mock_item(0), mock_item(4)]
    mock_pc_instance = MagicMock()
    mock_pc_instance.inference.rerank.return_value = mock_result

    with patch("app.chat.rag_service.Pinecone", return_value=mock_pc_instance):
        result = _rerank("query", docs, top_n=3)

    assert len(result) == 3
    assert result[0] == docs[2]
    assert result[1] == docs[0]
    assert result[2] == docs[4]


def test_rerank_fallback_on_exception():
    docs = [_doc(f"file{i}.md") for i in range(5)]
    with patch("app.chat.rag_service.Pinecone", side_effect=Exception("API error")):
        result = _rerank("query", docs, top_n=3)
    assert result == docs[:3]


def test_rerank_empty_docs():
    with patch("app.chat.rag_service.Pinecone") as mock_pc:
        result = _rerank("query", [], top_n=3)
        mock_pc.assert_not_called()
    assert result == []


def test_rerank_empty_pinecone_response():
    docs = [_doc(f"file{i}.md") for i in range(5)]
    mock_result = MagicMock()
    mock_result.data = []
    mock_pc_instance = MagicMock()
    mock_pc_instance.inference.rerank.return_value = mock_result
    with patch("app.chat.rag_service.Pinecone", return_value=mock_pc_instance):
        result = _rerank("query", docs, top_n=3)
    assert result == []


# ── rag_query ─────────────────────────────────────────────────────────────────

def _make_retriever(docs):
    """Return a mock retriever whose .invoke() yields docs."""
    mock = MagicMock()
    mock.invoke.return_value = docs
    return mock


def _passthrough_rerank(query, docs, top_n):
    return docs


def test_rag_query_unknown_role_returns_fallback():
    result = rag_query("anything", "unknown_role")
    assert result["answer"] == "I don't have access to that information."
    assert result["sources"] == []
    assert result["role"] == "unknown_role"


def test_rag_query_empty_retrieval_returns_fallback():
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever:
        mock_get_retriever.return_value = _make_retriever([])
        result = rag_query("what is the budget?", "finance")
    assert result["answer"] == "I don't have access to that information."
    assert result["sources"] == []
    assert result["role"] == "finance"


def test_rag_query_happy_path():
    docs = [_doc("finance.md", "Budget"), _doc("general.md", "Policy")]
    mock_llm = RunnableLambda(lambda _: "The budget is $1M.")
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever, \
         patch("app.chat.rag_service._rerank", side_effect=_passthrough_rerank), \
         patch("app.chat.rag_service._get_llm", return_value=mock_llm):
        mock_get_retriever.return_value = _make_retriever(docs)
        result = rag_query("what is the budget?", "finance")
    assert result["answer"] == "The budget is $1M."
    assert result["role"] == "finance"
    assert len(result["sources"]) == 2


def test_rag_query_response_keys():
    docs = [_doc()]
    mock_llm = RunnableLambda(lambda _: "answer")
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever, \
         patch("app.chat.rag_service._rerank", side_effect=_passthrough_rerank), \
         patch("app.chat.rag_service._get_llm", return_value=mock_llm):
        mock_get_retriever.return_value = _make_retriever(docs)
        result = rag_query("query", "finance")
    assert set(result.keys()) == {"answer", "sources", "role"}


def test_rag_query_role_passthrough():
    docs = [_doc()]
    mock_llm = RunnableLambda(lambda _: "answer")
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever, \
         patch("app.chat.rag_service._rerank", side_effect=_passthrough_rerank), \
         patch("app.chat.rag_service._get_llm", return_value=mock_llm):
        mock_get_retriever.return_value = _make_retriever(docs)
        result = rag_query("query", "engineering")
    assert result["role"] == "engineering"


def test_rag_query_retriever_called_with_correct_depts_and_k():
    docs = [_doc()]
    mock_llm = RunnableLambda(lambda _: "answer")
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever, \
         patch("app.chat.rag_service._rerank", side_effect=_passthrough_rerank), \
         patch("app.chat.rag_service._get_llm", return_value=mock_llm):
        mock_get_retriever.return_value = _make_retriever(docs)
        rag_query("query", "finance")
    args, kwargs = mock_get_retriever.call_args
    assert set(args[0]) == {"finance", "general"}
    assert kwargs.get("k", args[1] if len(args) > 1 else None) == 6


def test_rag_query_sources_deduplication():
    docs = [_doc("report.md", "Q1"), _doc("report.md", "Q1")]
    mock_llm = RunnableLambda(lambda _: "answer")
    with patch("app.chat.rag_service.get_retriever") as mock_get_retriever, \
         patch("app.chat.rag_service._rerank", side_effect=_passthrough_rerank), \
         patch("app.chat.rag_service._get_llm", return_value=mock_llm):
        mock_get_retriever.return_value = _make_retriever(docs)
        result = rag_query("query", "finance")
    assert result["sources"] == [{"file": "report.md", "section": "Q1"}]
