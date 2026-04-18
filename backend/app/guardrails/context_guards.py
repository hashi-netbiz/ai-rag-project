import re

from langchain_core.documents import Document

from app.guardrails.input_guards import INJECTION_PATTERNS
from app.guardrails.models import GuardrailAction, GuardrailEvent


def sanitize_context_docs(
    docs: list[Document],
    patterns: list[str] | None = None,
) -> tuple[list[Document], GuardrailEvent]:
    """Strip prompt injection payloads from retrieved document content.

    Returns new Document objects (originals untouched) with injections replaced
    by [REDACTED]. All metadata is preserved unchanged.
    """
    active_patterns = patterns if patterns is not None else INJECTION_PATTERNS
    sanitized_docs: list[Document] = []
    any_sanitized = False

    for doc in docs:
        content = doc.page_content
        for pattern in active_patterns:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)

        new_doc = Document(page_content=content, metadata=dict(doc.metadata))
        sanitized_docs.append(new_doc)

        if content != doc.page_content:
            any_sanitized = True

    action = GuardrailAction.SANITIZED if any_sanitized else GuardrailAction.PASSED
    return sanitized_docs, GuardrailEvent(
        layer="context",
        check="context_sanitization",
        action=action,
        detail="Injection patterns stripped from document content" if any_sanitized else "",
    )


def check_source_trust(
    docs: list[Document],
    allowed_departments: list[str],
) -> GuardrailEvent:
    """Verify every doc's department metadata is in allowed_departments.

    Defense-in-depth check — RBAC is already enforced at retrieval, but this
    catches any bypass or misconfiguration. Docs with absent department metadata
    are treated as general/public and allowed through.
    """
    for doc in docs:
        dept = doc.metadata.get("department")
        if dept is not None and dept not in allowed_departments:
            return GuardrailEvent(
                layer="context",
                check="source_trust",
                action=GuardrailAction.BLOCKED,
                detail=f"Untrusted document department: {dept}",
                metadata={"department": dept, "allowed": allowed_departments},
            )
    return GuardrailEvent(layer="context", check="source_trust", action=GuardrailAction.PASSED)


def check_relevance_threshold(
    docs: list[Document],
    threshold: float = 0.0,
) -> GuardrailEvent:
    """Flag retrieval as low-quality if all reranker scores are below threshold.

    A threshold of 0.0 (default) disables the check — all docs pass.
    If any doc is missing relevance_score metadata, the check passes through
    to avoid over-blocking on missing data.
    """
    if threshold <= 0.0:
        return GuardrailEvent(
            layer="context", check="relevance_threshold", action=GuardrailAction.PASSED
        )

    scores = [
        doc.metadata["relevance_score"]
        for doc in docs
        if "relevance_score" in doc.metadata
    ]

    if scores and all(score < threshold for score in scores):
        return GuardrailEvent(
            layer="context",
            check="relevance_threshold",
            action=GuardrailAction.FLAGGED,
            detail=f"All relevance scores below threshold {threshold}: {scores}",
            metadata={"scores": scores, "threshold": threshold},
        )
    return GuardrailEvent(
        layer="context", check="relevance_threshold", action=GuardrailAction.PASSED
    )
