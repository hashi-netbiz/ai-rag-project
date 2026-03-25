from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.models import LoginRequest, Token, User
from app.auth.service import authenticate_user, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: LoginRequest) -> Token:
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return Token(access_token=token, token_type="bearer", role=user["role"])


@router.get("/me", response_model=User)
def me(current_user: dict = Depends(get_current_user)) -> User:
    return User(**current_user)
