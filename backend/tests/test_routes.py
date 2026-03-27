from unittest.mock import patch
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_valid(client):
    r = client.post("/auth/login", json={"username": "alice", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": "pass123"})
    assert r.status_code == 401


def test_login_missing_fields(client):
    r = client.post("/auth/login", json={"username": "alice"})
    assert r.status_code == 422


@pytest.mark.parametrize("username,role", [
    ("alice", "finance"),
    ("bob", "marketing"),
    ("carol", "hr"),
    ("dave", "engineering"),
    ("eve", "c_level"),
    ("frank", "employee"),
])
def test_all_users_login(client, username, role):
    r = client.post("/auth/login", json={"username": username, "password": "pass123"})
    assert r.status_code == 200


def test_me_valid(client, alice_token):
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {alice_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "alice"
    assert data["role"] == "finance"


def test_me_no_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_garbage_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_chat_query_unauthenticated(client):
    r = client.post("/chat/query", json={"query": "What is gross margin?"})
    assert r.status_code == 401


def test_chat_query_authenticated(client, alice_token):
    mock_result = {
        "answer": "The gross margin is 62%.",
        "sources": [{"file": "financial_summary.md", "section": "Q3"}],
        "role": "finance",
    }
    with patch("app.chat.router.rag_query", return_value=mock_result):
        r = client.post(
            "/chat/query",
            json={"query": "What is gross margin?"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "The gross margin is 62%."
    assert len(data["sources"]) == 1
    assert data["role"] == "finance"


def test_chat_query_missing_body(client, alice_token):
    r = client.post(
        "/chat/query",
        json={},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert r.status_code == 422


def test_chat_query_no_access_passthrough(client, frank_token):
    mock_result = {
        "answer": "I don't have access to that information.",
        "sources": [],
        "role": "employee",
    }
    with patch("app.chat.router.rag_query", return_value=mock_result):
        r = client.post(
            "/chat/query",
            json={"query": "What is gross margin?"},
            headers={"Authorization": f"Bearer {frank_token}"},
        )
    assert r.status_code == 200
    assert "don't have access" in r.json()["answer"]
