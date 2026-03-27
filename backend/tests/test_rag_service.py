from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from app.chat.rag_service import _extract_sources, _rerank


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
