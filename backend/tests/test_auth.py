import pytest
from jose import jwt
from app.auth.service import verify_password, authenticate_user, create_access_token, USERS
from app.config import settings


def test_verify_password_correct():
    hashed = USERS["alice"]["hashed_password"]
    assert verify_password("pass123", hashed) is True


def test_verify_password_wrong():
    hashed = USERS["alice"]["hashed_password"]
    assert verify_password("wrongpass", hashed) is False


def test_verify_password_empty():
    hashed = USERS["alice"]["hashed_password"]
    assert verify_password("", hashed) is False


def test_authenticate_user_valid():
    user = authenticate_user("alice", "pass123")
    assert user is not None
    assert user["role"] == "finance"


def test_authenticate_user_wrong_password():
    assert authenticate_user("alice", "wrong") is None


def test_authenticate_user_unknown():
    assert authenticate_user("nobody", "pass123") is None


@pytest.mark.parametrize("username,role", [
    ("alice", "finance"),
    ("bob", "marketing"),
    ("carol", "hr"),
    ("dave", "engineering"),
    ("eve", "c_level"),
    ("frank", "employee"),
])
def test_all_demo_users_authenticate(username, role):
    user = authenticate_user(username, "pass123")
    assert user is not None
    assert user["role"] == role


def test_create_access_token_fields():
    token = create_access_token({"sub": "alice", "role": "finance"})
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "alice"
    assert payload["role"] == "finance"
    assert "exp" in payload
