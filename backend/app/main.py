import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Set LangChain/Langsmith env vars before any LangChain imports resolve tracing config...very important
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

from app.auth.router import router as auth_router
from app.chat.router import router as chat_router

app = FastAPI(title="RAG RBAC Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

