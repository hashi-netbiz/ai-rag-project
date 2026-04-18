from fastapi import HTTPException, status
from langchain_core.documents import Document

from app.guardrails.context_guards import (
    check_relevance_threshold,
    check_source_trust,
    sanitize_context_docs,
)
from app.guardrails.input_guards import (
    check_pii,
    check_prompt_injection,
    check_query_length,
)
from app.guardrails.models import GuardrailAction, GuardrailEvent
from app.guardrails.output_guards import (
    check_faithfulness,
    check_refusal,
    check_response_length,
)


def run_input_guardrails(
    query: str,
    max_query_length: int = 500,
    injection_patterns: list[str] | None = None,
) -> tuple[str, list[GuardrailEvent]]:
    """Run all input guardrails in order: length → injection → PII.

    Hard blocks (length, injection) raise HTTPException(400) immediately.
    PII is sanitized and the redacted query is returned.
    Returns (final_query, all_events).
    """
    events: list[GuardrailEvent] = []

    length_event = check_query_length(query, max_length=max_query_length)
    events.append(length_event)
    if length_event.action == GuardrailAction.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"guardrail": "query_length", "reason": length_event.detail},
        )

    injection_event = check_prompt_injection(query, patterns=injection_patterns)
    events.append(injection_event)
    if injection_event.action == GuardrailAction.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"guardrail": "prompt_injection", "reason": injection_event.detail},
        )

    pii_event = check_pii(query)
    events.append(pii_event)
    if pii_event.action == GuardrailAction.SANITIZED:
        query = pii_event.metadata["sanitized_query"]

    return query, events


def run_context_guardrails(
    docs: list[Document],
    allowed_departments: list[str],
    relevance_threshold: float = 0.0,
) -> tuple[list[Document], bool, list[GuardrailEvent]]:
    """Run all context guardrails in order: source_trust → relevance → sanitize.

    source_trust block raises HTTPException(403).
    relevance FLAGGED returns should_fallback=True — caller returns canned answer.
    sanitize strips injections from doc content and returns new Document objects.
    Returns (final_docs, should_fallback, all_events).
    """
    events: list[GuardrailEvent] = []

    trust_event = check_source_trust(docs, allowed_departments)
    events.append(trust_event)
    if trust_event.action == GuardrailAction.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"guardrail": "source_trust", "reason": trust_event.detail},
        )

    relevance_event = check_relevance_threshold(docs, threshold=relevance_threshold)
    events.append(relevance_event)
    if relevance_event.action == GuardrailAction.FLAGGED:
        return docs, True, events

    docs, sanitize_event = sanitize_context_docs(docs)
    events.append(sanitize_event)

    return docs, False, events


def run_output_guardrails(
    answer: str,
    sources: list[dict],
    max_response_length: int = 2000,
    min_answer_length_faithfulness: int = 50,
) -> tuple[str, list[GuardrailEvent]]:
    """Run all output guardrails in order: refusal → faithfulness → response_length.

    All are non-blocking. Returns (final_answer, all_events).
    final_answer may be truncated if it exceeded max_response_length.
    """
    events: list[GuardrailEvent] = []

    refusal_event = check_refusal(answer)
    events.append(refusal_event)

    faithfulness_event = check_faithfulness(
        answer, sources, min_answer_length=min_answer_length_faithfulness
    )
    events.append(faithfulness_event)

    answer, length_event = check_response_length(answer, max_length=max_response_length)
    events.append(length_event)

    return answer, events
