from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.service import get_current_user
from app.chat.rag_service import rag_query

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


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> QueryResponse:
    role = current_user["role"]
    result = rag_query(query=request.query, role=role)
    return QueryResponse(
        answer=result["answer"],
        sources=[SourceCitation(**s) for s in result["sources"]],
        role=result["role"],
    )
