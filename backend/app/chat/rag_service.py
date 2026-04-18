import logging

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langsmith import traceable
from pinecone import Pinecone

from app.config import settings
from app.guardrails import run_context_guardrails, run_output_guardrails
from app.rbac.permissions import get_allowed_departments
from app.vector_store.pinecone_client import get_retriever

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
NO_ACCESS_MSG = "I don't have access to that information."

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


def _rerank(query: str, docs: list[Document], top_n: int = 3) -> list[Document]:
    """Rerank retrieved docs using Pinecone bge-reranker-v2-m3, return top_n."""
    if len(docs) <= top_n:
        return docs
    try:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        result = pc.inference.rerank(
            model="bge-reranker-v2-m3",
            query=query,
            documents=[doc.page_content for doc in docs],
            top_n=top_n,
            return_documents=False,
        )
        return [docs[item.index] for item in result.data]
    except Exception:
        return docs[:top_n]


def _extract_sources(docs: list[Document]) -> list[dict[str, str]]:
    """Deduplicate and extract source citations from retrieved documents."""
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, str]] = []

    for doc in docs:
        source_file = str(doc.metadata.get("source_file", "")).strip()
        section = str(doc.metadata.get("section", "")).strip()

        key = (source_file, section)

        if key not in seen:
            seen.add(key)
            sources.append({"file": source_file, "section": section})

    return sources


@traceable
def rag_query(query: str, role: str) -> dict:
    """Run a role-restricted RAG query. Returns answer, sources, role, and guardrail_flags."""
    allowed_depts = get_allowed_departments(role)

    if not allowed_depts:
        return {
            "answer": NO_ACCESS_MSG,
            "sources": [],
            "role": role,
            "guardrail_flags": [],
        }

    # Retrieve relevant chunks (RBAC filter applied server-side)
    retriever = get_retriever(allowed_depts, k=6)
    docs = retriever.invoke(query)

    if not docs:
        return {
            "answer": NO_ACCESS_MSG,
            "sources": [],
            "role": role,
            "guardrail_flags": [],
        }

    # Rerank to top 3 most relevant chunks
    docs = _rerank(query, docs, top_n=3)

    # [B] Context guardrails — source trust, relevance threshold, context sanitization
    docs, should_fallback, ctx_events = run_context_guardrails(
        docs,
        allowed_depts,
        relevance_threshold=settings.guardrail_relevance_threshold,
    )
    ctx_flags = [e.check for e in ctx_events if e.action != "passed"]

    if should_fallback:
        return {
            "answer": NO_ACCESS_MSG,
            "sources": [],
            "role": role,
            "guardrail_flags": ctx_flags,
        }

    # Build context string
    context = "\n\n---\n\n".join(doc.page_content for doc in docs)

    # Generate answer via Groq
    chain = _prompt | _get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context, "question": query})

    sources = _extract_sources(docs)

    # [C] Output guardrails — refusal detection, faithfulness, response length
    answer, out_events = run_output_guardrails(
        answer,
        sources,
        max_response_length=settings.guardrail_max_response_length,
        min_answer_length_faithfulness=settings.guardrail_min_answer_length_faithfulness,
    )

    all_flags = ctx_flags + [e.check for e in out_events if e.action != "passed"]

    if all_flags:
        logger.info("guardrail_flags=%s role=%s", all_flags, role)

    # [D] LangSmith trace enrichment
    try:
        from langsmith import get_current_run_tree
        run = get_current_run_tree()
        if run and all_flags:
            run.add_metadata({"guardrail_flags": all_flags})
    except Exception:
        pass

    return {
        "answer": answer,
        "sources": sources,
        "role": role,
        "guardrail_flags": all_flags,
    }
