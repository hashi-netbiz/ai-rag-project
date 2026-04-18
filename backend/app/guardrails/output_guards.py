from app.guardrails.models import GuardrailAction, GuardrailEvent

REFUSAL_PHRASES: list[str] = [
    "i don't have access to that information",
    "i cannot",
    "i am not able to",
    "as an ai",
    "i'm not allowed",
    "i cannot assist with",
    "i'm sorry, but",
    "i must decline",
]


def check_refusal(answer: str) -> GuardrailEvent:
    """Flag answers that contain LLM refusal phrases (monitoring only, non-blocking)."""
    lower = answer.lower()
    for phrase in REFUSAL_PHRASES:
        if phrase in lower:
            return GuardrailEvent(
                layer="output",
                check="refusal_detection",
                action=GuardrailAction.FLAGGED,
                detail=f"Refusal phrase detected: '{phrase}'",
                metadata={"matched_phrase": phrase},
            )
    return GuardrailEvent(layer="output", check="refusal_detection", action=GuardrailAction.PASSED)


def check_faithfulness(
    answer: str,
    sources: list[dict],
    min_answer_length: int = 50,
) -> GuardrailEvent:
    """Flag substantive answers with no source citations as possible hallucinations.

    Heuristic: len(answer) >= min_answer_length AND len(sources) == 0.
    Short answers (e.g. the canned fallback) with no sources are legitimate — not flagged.
    No second LLM call; zero latency cost.
    """
    if len(answer) >= min_answer_length and len(sources) == 0:
        return GuardrailEvent(
            layer="output",
            check="faithfulness",
            action=GuardrailAction.FLAGGED,
            detail="Substantive answer with no source citations — possible hallucination",
            metadata={"answer_length": len(answer), "source_count": 0},
        )
    return GuardrailEvent(layer="output", check="faithfulness", action=GuardrailAction.PASSED)


def check_response_length(
    answer: str,
    max_length: int = 2000,
) -> tuple[str, GuardrailEvent]:
    """Truncate answers that exceed max_length characters."""
    if len(answer) > max_length:
        truncated = answer[:max_length] + "..."
        return truncated, GuardrailEvent(
            layer="output",
            check="response_length",
            action=GuardrailAction.SANITIZED,
            detail=f"Answer truncated from {len(answer)} to {max_length} characters",
            metadata={"original_length": len(answer), "max_length": max_length},
        )
    return answer, GuardrailEvent(
        layer="output", check="response_length", action=GuardrailAction.PASSED
    )
