from dataclasses import dataclass, field
from enum import Enum


class GuardrailAction(str, Enum):
    BLOCKED = "blocked"      # hard stop; HTTPException raised upstream
    FLAGGED = "flagged"      # soft flag; included in guardrail_flags
    SANITIZED = "sanitized"  # content mutated; pipeline continues
    PASSED = "passed"        # no issue found


@dataclass
class GuardrailEvent:
    layer: str                               # "input" | "context" | "output"
    check: str                               # e.g. "query_length", "pii_detection"
    action: GuardrailAction
    detail: str = ""                         # human-readable reason
    metadata: dict = field(default_factory=dict)  # e.g. {"matched": "ignore previous"}
