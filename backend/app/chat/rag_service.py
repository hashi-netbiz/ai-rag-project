from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langsmith import traceable

from app.config import settings
from app.rbac.permissions import get_allowed_departments
from app.vector_store.pinecone_client import get_retriever

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a company knowledge assistant. Answer questions based ONLY on the provided context.
If the context does not contain relevant information to answer the question, respond with exactly:
"I don't have access to that information."
Do not use any knowledge outside of the provided context. Be concise and factual."""

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])


def _get_llm() -> ChatGroq:
    return ChatGroq(model=GROQ_MODEL, groq_api_key=settings.groq_api_key)


def _extract_sources(docs: list[Document]) -> list[dict]:
    """Deduplicate and extract source citations from retrieved documents."""
    seen: set[tuple] = set()
    sources: list[dict] = []
    for doc in docs:
        file = doc.metadata.get("source_file", "")
        section = doc.metadata.get("section", "")
        key = (file, section)
        if key not in seen:
            seen.add(key)
            sources.append({"file": file, "section": section})
    return sources


@traceable
def rag_query(query: str, role: str) -> dict:
    """Run a role-restricted RAG query. Returns answer, sources, and role."""
    allowed_depts = get_allowed_departments(role)

    if not allowed_depts:
        return {
            "answer": "I don't have access to that information.",
            "sources": [],
            "role": role,
        }

    # Retrieve relevant chunks (RBAC filter applied server-side)
    retriever = get_retriever(allowed_depts)
    docs = retriever.invoke(query)

    if not docs:
        return {
            "answer": "I don't have access to that information.",
            "sources": [],
            "role": role,
        }

    # Build context string
    context = "\n\n---\n\n".join(doc.page_content for doc in docs)

    # Generate answer via Groq
    chain = _prompt | _get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context, "question": query})

    return {
        "answer": answer,
        "sources": _extract_sources(docs),
        "role": role,
    }
