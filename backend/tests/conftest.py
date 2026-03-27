import os
import pytest

os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GOOGLE_API_KEY", "test")
os.environ.setdefault("PINECONE_API_KEY", "test")
os.environ.setdefault("PINECONE_INDEX_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("LANGCHAIN_API_KEY", "test")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_PROJECT", "test")

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def alice_token(client):
    return client.post("/auth/login", json={"username": "alice", "password": "pass123"}).json()["access_token"]


@pytest.fixture(scope="session")
def frank_token(client):
    return client.post("/auth/login", json={"username": "frank", "password": "pass123"}).json()["access_token"]
