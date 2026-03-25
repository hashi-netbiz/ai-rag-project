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
