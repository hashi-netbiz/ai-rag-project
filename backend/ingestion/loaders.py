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
