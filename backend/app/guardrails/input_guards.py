import re

from app.guardrails.models import GuardrailAction, GuardrailEvent

INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(?:\w+\s+)?(previous|all|above|prior)\s+(instructions?|prompts?|context)",
    r"system\s*prompt",
    r"you\s+are\s+now\s+(?:a|an|the)\s+\w+",
    r"forget\s+(everything|all|your|previous)",
    r"jailbreak",
    r"disregard\s+(your|all|previous|the)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a|an)",
    r"do\s+anything\s+now",
    r"developer\s+mode",
]

PII_PATTERNS: dict[str, str] = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
}


def check_query_length(query: str, max_length: int = 500) -> GuardrailEvent:
    """Block queries that exceed max_length characters."""
    if len(query) > max_length:
        return GuardrailEvent(
            layer="input",
            check="query_length",
            action=GuardrailAction.BLOCKED,
            detail=f"Query length {len(query)} exceeds maximum {max_length}",
        )
    return GuardrailEvent(layer="input", check="query_length", action=GuardrailAction.PASSED)


def check_prompt_injection(
    query: str, patterns: list[str] | None = None
) -> GuardrailEvent:
    """Detect prompt injection attempts via regex pattern matching."""
    active_patterns = patterns if patterns is not None else INJECTION_PATTERNS
    for pattern in active_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return GuardrailEvent(
                layer="input",
                check="prompt_injection",
                action=GuardrailAction.BLOCKED,
                detail=f"Matched injection pattern: {pattern}",
                metadata={"matched_text": match.group(0)},
            )
    return GuardrailEvent(layer="input", check="prompt_injection", action=GuardrailAction.PASSED)


def check_pii(query: str) -> GuardrailEvent:
    """Detect and redact PII from query. Sanitized query stored in event.metadata."""
    sanitized = query
    found_types: list[str] = []

    for pii_type, pattern in PII_PATTERNS.items():
        new_sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        if new_sanitized != sanitized:
            found_types.append(pii_type)
            sanitized = new_sanitized

    if found_types:
        return GuardrailEvent(
            layer="input",
            check="pii_detection",
            action=GuardrailAction.SANITIZED,
            detail=f"PII types detected and redacted: {', '.join(found_types)}",
            metadata={"pii_types_found": found_types, "sanitized_query": sanitized},
        )
    return GuardrailEvent(layer="input", check="pii_detection", action=GuardrailAction.PASSED)
