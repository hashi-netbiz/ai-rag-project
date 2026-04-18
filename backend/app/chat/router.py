from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.service import get_current_user
from app.chat.rag_service import rag_query
from app.config import settings
from app.guardrails import run_input_guardrails

router = APIRouter(prefix="/chat", tags=["chat"])


class QueryRequest(BaseModel):
    query: str


class SourceCitation(BaseModel):
    file: str
    section: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    role: str
    guardrail_flags: list[str] = []


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> QueryResponse:
    role = current_user["role"]

    # [A] Input guardrails — raises HTTPException(400) on hard blocks;
    # returns sanitized query (PII redacted) for soft cases.
    sanitized_query, input_events = run_input_guardrails(
        request.query,
        max_query_length=settings.guardrail_max_query_length,
    )

    result = rag_query(query=sanitized_query, role=role)

    # Collect flags from input layer and from downstream layers
    pipeline_flags: list[str] = result.get("guardrail_flags", [])
    input_flags = [e.check for e in input_events if e.action != "passed"]
    all_flags = input_flags + pipeline_flags

    return QueryResponse(
        answer=result["answer"],
        sources=[SourceCitation(**s) for s in result["sources"]],
        role=result["role"],
        guardrail_flags=all_flags,
    )
