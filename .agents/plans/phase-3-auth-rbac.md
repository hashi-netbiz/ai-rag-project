# Feature: Phase 3 — Auth & RBAC

The following plan should be complete, but validate all imports and API signatures against the installed packages before implementing. All packages are already installed in `backend/.venv`.

Pay special attention to `datetime.now(timezone.utc)` — the older `datetime.utcnow()` is deprecated in Python 3.11+. Use the timezone-aware form.

## Feature Description

Implement JWT authentication with bcrypt password hashing, a demo user store for all 6 roles, and the RBAC role→department mapping. Expose `POST /auth/login` and `GET /auth/me` endpoints. Wire everything into `main.py` with CORS so the server can actually run. After this phase the backend is startable and authentication is fully testable.

## User Story

As a developer,
I want a running FastAPI server with working JWT login and role extraction,
So that Phase 4 can add the RAG pipeline behind an authenticated endpoint without touching auth again.

## Problem Statement

`auth/models.py`, `auth/service.py`, `auth/router.py` are all stubs. `main.py` is also a stub — the server cannot start. Phase 4 requires a working `get_current_user` FastAPI dependency and a running app.

## Solution Statement

Implement in dependency order:
1. `auth/models.py` — Pydantic schemas (no dependencies)
2. `auth/service.py` — password hashing, JWT creation/verification, demo user store, `get_current_user` dependency
3. `auth/router.py` — `/auth/login` and `/auth/me` endpoints
4. `main.py` — FastAPI app, CORS, mount auth router, health endpoint

`config.py` and `rbac/permissions.py` are **already fully implemented** — do not modify them.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Low
**Primary Systems Affected**: `backend/app/auth/`, `backend/app/main.py`
**Dependencies**: python-jose 3.5.0, passlib 1.7.4, fastapi 0.135.2, pydantic-settings 2.13.1 — all installed

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `backend/app/config.py` — **ALREADY DONE**. Has `settings.jwt_secret_key`, `settings.jwt_algorithm`, `settings.jwt_expire_minutes`. Import via `from app.config import settings`.
- `backend/app/rbac/permissions.py` — **ALREADY DONE**. Has `ROLE_PERMISSIONS` dict and `get_allowed_departments(role)`. Auth doesn't call this — it's used in Phase 4.
- `backend/.env.example` — shows `JWT_SECRET_KEY`, `JWT_ALGORITHM=HS256`, `JWT_EXPIRE_MINUTES=60`
- `backend/app/auth/models.py` — stub, implement here
- `backend/app/auth/service.py` — stub, implement here
- `backend/app/auth/router.py` — stub, implement here
- `backend/app/main.py` — stub, implement here (partial — chat router stays as stub)

### New Files to Create

None — all files exist as stubs. Overwrite stubs with implementations.

### Verified API Signatures (from installed packages)

```python
# python-jose 3.5.0
from jose import JWTError, jwt
jwt.encode(payload: dict, key: str, algorithm: str) -> str
jwt.decode(token: str, key: str, algorithms: list[str]) -> dict  # raises JWTError on failure

# passlib 1.7.4
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context.hash(password: str) -> str
pwd_context.verify(plain: str, hashed: str) -> bool

# FastAPI OAuth2
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Injects Bearer token string as dependency
```

### Patterns to Follow

**Settings access** (from config.py pattern):
```python
from app.config import settings
# Use: settings.jwt_secret_key, settings.jwt_algorithm, settings.jwt_expire_minutes
```

**FastAPI router pattern** (to mirror in Phase 4):
```python
router = APIRouter(prefix="/auth", tags=["auth"])
# Mounted in main.py via: app.include_router(auth_router)
```

**Dependency injection pattern** (critical — Phase 4 copies this):
```python
current_user: dict = Depends(get_current_user)
```

**Demo user store** — pre-hash passwords at module import time (not lazily) so startup is deterministic:
```python
USERS: dict[str, dict] = {
    "alice": {"username": "alice", "hashed_password": pwd_context.hash("pass123"), "role": "finance"},
    ...
}
```

---

## IMPLEMENTATION PLAN

### Phase 3A: Schemas
`auth/models.py` — three Pydantic models, no imports from other app modules.

### Phase 3B: Service layer
`auth/service.py` — all business logic. Imports from `app.config`. No router imports.

### Phase 3C: Router
`auth/router.py` — thin HTTP layer. Imports from `app.auth.models` and `app.auth.service`.

### Phase 3D: App entry point
`main.py` — wires everything. Imports `auth_router` only (chat router stays stub until Phase 4).

---

## STEP-BY-STEP TASKS

### TASK 1 — IMPLEMENT `backend/app/auth/models.py`

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class User(BaseModel):
    username: str
    role: str
```

- **GOTCHA**: `Token` has a `role` field — this is non-standard but required by the PRD (`POST /auth/login` response includes `role`).
- **VALIDATE**:
```bash
cd backend && uv run python -c "from app.auth.models import LoginRequest, Token, User; print('models OK')"
```

---

### TASK 2 — IMPLEMENT `backend/app/auth/service.py`

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Demo user store — passwords hashed at import time
USERS: dict[str, dict] = {
    "alice": {"username": "alice", "hashed_password": pwd_context.hash("pass123"), "role": "finance"},
    "bob":   {"username": "bob",   "hashed_password": pwd_context.hash("pass123"), "role": "marketing"},
    "carol": {"username": "carol", "hashed_password": pwd_context.hash("pass123"), "role": "hr"},
    "dave":  {"username": "dave",  "hashed_password": pwd_context.hash("pass123"), "role": "engineering"},
    "eve":   {"username": "eve",   "hashed_password": pwd_context.hash("pass123"), "role": "c_level"},
    "frank": {"username": "frank", "hashed_password": pwd_context.hash("pass123"), "role": "employee"},
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> dict | None:
    user = USERS.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return {"username": username, "role": role}
```

- **GOTCHA**: Use `datetime.now(timezone.utc)` — NOT `datetime.utcnow()` (deprecated in Python 3.11).
- **GOTCHA**: `jwt.decode` requires `algorithms` as a list, not a string.
- **GOTCHA**: `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")` — the `tokenUrl` value doesn't affect runtime behavior but must be a valid path string for OpenAPI docs.
- **VALIDATE**:
```bash
cd backend && uv run python -c "
from app.auth.service import authenticate_user, create_access_token, USERS
assert authenticate_user('alice', 'pass123') is not None
assert authenticate_user('alice', 'wrong') is None
assert authenticate_user('nobody', 'pass123') is None
token = create_access_token({'sub': 'alice', 'role': 'finance'})
assert isinstance(token, str) and len(token) > 20
print('service OK, token:', token[:30], '...')
"
```

---

### TASK 3 — IMPLEMENT `backend/app/auth/router.py`

```python
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
```

- **VALIDATE**:
```bash
cd backend && uv run python -c "from app.auth.router import router; print('router OK, routes:', [r.path for r in router.routes])"
```

---

### TASK 4 — IMPLEMENT `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router

app = FastAPI(title="RAG RBAC Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- **NOTE**: The chat router is NOT mounted here yet — that's Phase 4. Keeping `main.py` minimal ensures Phase 3 is independently testable.
- **GOTCHA**: `allow_origins` must be a list, not a string. `"http://localhost:3000"` (no trailing slash).
- **VALIDATE**:
```bash
cd backend && uv run python -c "from app.main import app; print('main OK, routes:', [r.path for r in app.routes])"
```

---

### TASK 5 — START SERVER AND RUN LIVE CURL TESTS

Start the server in the background:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 2
```

Test health endpoint:
```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

Test login — valid credentials:
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "pass123"}'
# Expected: {"access_token":"<jwt>","token_type":"bearer","role":"finance"}
```

Test login — invalid credentials:
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "wrong"}'
# Expected: {"detail":"Incorrect username or password"}
```

Test /auth/me with token:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "pass123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"username":"alice","role":"finance"}
```

Stop the background server after testing:
```bash
kill %1 2>/dev/null || true
```

---

## TESTING STRATEGY

### Unit Tests (no server needed)
All Task 1–4 inline `uv run python -c` validation commands qualify as unit-level tests.

### Integration Tests (server required)
Task 5 curl commands cover all PRD-specified API behaviors.

### Edge Cases
- Wrong password → 401
- Unknown username → 401 (same message, no username enumeration)
- Missing/invalid Bearer token on `/auth/me` → 401
- Expired token → 401 (handled automatically by `jwt.decode`)

---

## VALIDATION COMMANDS

### Level 1: Import chain
```bash
cd backend && uv run python -c "
from app.auth.models import LoginRequest, Token, User
from app.auth.service import authenticate_user, create_access_token, get_current_user
from app.auth.router import router
from app.main import app
print('ALL IMPORTS OK')
print('Registered routes:', [r.path for r in app.routes])
"
```

### Level 2: Business logic
```bash
cd backend && uv run python -c "
from app.auth.service import authenticate_user, create_access_token
from jose import jwt
from app.config import settings

# Auth success
u = authenticate_user('eve', 'pass123')
assert u['role'] == 'c_level', f'Expected c_level, got {u[\"role\"]}'

# Auth failure
assert authenticate_user('alice', 'badpass') is None

# Token round-trip
token = create_access_token({'sub': 'alice', 'role': 'finance'})
payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
assert payload['sub'] == 'alice'
assert payload['role'] == 'finance'
print('LOGIC VALIDATION PASSED')
"
```

### Level 3: All 6 roles covered
```bash
cd backend && uv run python -c "
from app.auth.service import USERS
from app.rbac.permissions import ROLE_PERMISSIONS
user_roles = {u['role'] for u in USERS.values()}
rbac_roles = set(ROLE_PERMISSIONS.keys())
assert user_roles == rbac_roles, f'Mismatch: users={user_roles} rbac={rbac_roles}'
print('All 6 roles present in both USERS and ROLE_PERMISSIONS')
"
```

### Level 4: Live server curl tests
(See Task 5 above)

---

## ACCEPTANCE CRITERIA

- [ ] `POST /auth/login` returns `{access_token, token_type, role}` for all 6 demo users
- [ ] `POST /auth/login` returns 401 for wrong password (message: "Incorrect username or password")
- [ ] `GET /auth/me` returns `{username, role}` when valid Bearer token supplied
- [ ] `GET /auth/me` returns 401 when no/invalid token supplied
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] JWT contains `sub` (username), `role`, and `exp` claims
- [ ] All 6 roles present: finance, marketing, hr, engineering, c_level, employee
- [ ] `config.py` and `rbac/permissions.py` are NOT modified (already complete)
- [ ] Level 1–3 validation commands all pass
- [ ] Server starts with `uv run uvicorn app.main:app --port 8000`

---

## COMPLETION CHECKLIST

- [ ] Task 1 (models.py) — import validates
- [ ] Task 2 (service.py) — auth + token logic validates
- [ ] Task 3 (router.py) — routes visible
- [ ] Task 4 (main.py) — full import chain validates, all routes registered
- [ ] Task 5 — live curl tests pass for all 3 endpoints
- [ ] Level 1–3 validation commands pass

---

## NOTES

**`config.py` already done**: The `settings` singleton is imported at module level in `service.py`. Since `config.py` loads `.env` via pydantic-settings, the `.env` file in `backend/` must exist for the server to pick up `JWT_SECRET_KEY`. For import-only tests (no server), pydantic-settings falls back to the default `"dev-secret-change-in-production"` — tests still pass.

**`main.py` is minimal**: The chat router (`/chat/query`) is NOT added in Phase 3 — it's Phase 4's responsibility. This keeps Phase 3 self-contained and independently testable.

**Password hashing at import time**: Hashing all 6 demo passwords on first import adds ~0.5s startup overhead due to bcrypt work factor. Acceptable for MVP. In production, passwords would be stored pre-hashed in a database.

**`get_current_user` is the Phase 4 contract**: Phase 4's `chat/router.py` will call `current_user: dict = Depends(get_current_user)` and read `current_user["role"]`. The dict shape `{"username": str, "role": str}` must not change.
