# Plan: Phase 4 — CI Refactor + Production Promotion Workflow

## Context

Phase 4 of `NEW_PRD.md` completes the CI/CD loop by splitting the existing monolithic `ci-cd.yml` into three purpose-built workflows and wiring a configurable CORS `ALLOWED_ORIGINS` field into the backend. This enables the GitOps deployment pipeline (Phases 1–3) to function: `deploy.yml` becomes the source of ECR pushes and GitOps repo updates, `promote-prod.yml` gates production via GitHub Environments, and `ci.yml` gives PRs fast, cheap validation without touching ECR.

---

## Current State vs. Required

| Item | Current | Required |
|------|---------|----------|
| `ci.yml` | ❌ missing | ✅ PR validation (no ECR push) |
| `deploy.yml` | ❌ missing | ✅ post-merge: E2E → ECR (sha + staging-latest) → DAST → gitops-update |
| `promote-prod.yml` | ❌ missing | ✅ workflow_dispatch + approval gate + GitOps prod update |
| `ci-cd.yml` | ✅ exists (monolithic) | ❌ delete after replacement |
| `gitops-update` job | stub with TODOs | ✅ real `kustomize edit set image` + push |
| `ALLOWED_ORIGINS` in `config.py` | ❌ missing | ✅ `allowed_origins: str = "http://localhost:3000,http://localhost:3001"` |
| CORS in `main.py` | hardcoded list | ✅ `settings.allowed_origins.split(",")` |
| `ALLOWED_ORIGINS` in `.env.example` | ❌ missing | ✅ add entry |
| ECR image tags | `v1.<run_number>` only | ✅ `sha-<github.sha>` (immutable) + `staging-latest` (mutable) |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `.github/workflows/ci.yml` | **Create** |
| `.github/workflows/deploy.yml` | **Create** |
| `.github/workflows/promote-prod.yml` | **Create** |
| `.github/workflows/ci-cd.yml` | **Delete** |
| `backend/app/config.py` | **Edit** — add `allowed_origins` field |
| `backend/app/main.py` | **Edit** — read CORS origins from settings |
| `backend/.env.example` | **Edit** — add `ALLOWED_ORIGINS` entry |

---

## Implementation

### 1. `backend/app/config.py`

Add one field to `Settings`:

```python
allowed_origins: str = "http://localhost:3000,http://localhost:3001"
```

No other changes.

---

### 2. `backend/app/main.py`

Replace line 19 (hardcoded `allow_origins` list):

```python
# Before
allow_origins=["http://localhost:3000", "http://localhost:3001"],

# After
allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
```

---

### 3. `backend/.env.example`

Append after `LANGCHAIN_PROJECT`:

```
# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
```

---

### 4. `.github/workflows/ci.yml`

**Trigger:** `on: pull_request: branches: [master]`

**Jobs (reuse existing logic from `ci-cd.yml` verbatim):**
1. `gitleaks` — secret scan
2. `changes` — dorny/paths-filter
3. `sonarcloud` — SAST + pytest coverage
4. `sca` — OWASP Dependency-Check
5. `unit-tests` — pytest
6. `lint-and-typecheck` — frontend
7. `docker-build` — build + save `.tar` artifact (no push, tag `sha-${{ github.sha }}`)
8. `trivy` — container scan from artifact

**Key difference from `ci-cd.yml`:** No ECR push, no E2E, no DAST, no gitops-update.

---

### 5. `.github/workflows/deploy.yml`

**Trigger:** `on: push: branches: [master]`

**Jobs:**
1. `changes` — dorny/paths-filter
2. `e2e` — full docker-compose stack + `bash test_e2e.sh`
3. `docker-push` — needs `[e2e, changes]`
   - Authenticate via OIDC (`arn:aws:iam::891612574910:role/github-actions`)
   - Build and push with **two tags** per service:
     - `sha-${{ github.sha }}` (immutable)
     - `staging-latest` (mutable — requires ECR repos set to MUTABLE)
   - Retain existing `v1.${{ github.run_number }}` tag for legacy readability
4. `dast` — needs `[e2e]`, OWASP ZAP baseline against docker-compose stack
5. `gitops-update` — needs `[docker-push, dast]`
   - Checkout `${{ secrets.GITOPS_REPO }}` using `${{ secrets.GITOPS_TOKEN }}`
   - For each changed service (backend/frontend):
     ```bash
     cd k8s/staging
     kustomize edit set image \
       $BACKEND_IMAGE=$BACKEND_IMAGE:sha-${{ github.sha }}
     ```
   - Commit `"chore: update staging to sha-${{ github.sha }} [skip ci]"` and push

**Key difference from `ci-cd.yml`:** No SAST/SCA/unit-tests/lint (already passed on PR). gitops-update is real, not a stub.

---

### 6. `.github/workflows/promote-prod.yml`

**Trigger:** `workflow_dispatch` with inputs:
- `image_sha` (required) — e.g. `sha-abc1234`
- `services` (required, choice: `both` / `backend` / `frontend`, default `both`)
- `deploy_reason` (optional string)

**Job: `promote`** — runs in `environment: production` (blocks until GitHub required reviewer approves)

**Steps:**
1. Configure AWS credentials (OIDC)
2. Validate `image_sha` exists in ECR:
   ```bash
   aws ecr describe-images \
     --repository-name hashi-netbiz/ai-rag-project/backend \
     --image-ids imageTag=${{ inputs.image_sha }}
   ```
3. Checkout GitOps repo
4. `kustomize edit set image` on `k8s/prod/kustomization.yaml` for selected services
5. Commit:
   ```
   chore: promote ${{ inputs.image_sha }} to prod [approved by ${{ github.actor }}]
   ```
6. Push → ArgoCD detects + requires manual sync in UI

---

## Dependency Note

`deploy.yml` gitops-update uses `kustomize edit set image`. This requires the GitOps repo (`ai-rag-gitops`) to have `k8s/staging/kustomization.yaml` committed (Phase 2 deliverable). The `promote-prod.yml` similarly requires `k8s/prod/kustomization.yaml`. These files must exist before the first deploy workflow run succeeds.

---

## Verification

1. **Unit tests still pass:** `cd backend && uv run pytest tests/ -v` — the `allowed_origins` field change adds a new settings field with a default; all 52 tests should continue passing.

2. **Local dev CORS unchanged:** Start backend with no `.env` change — `settings.allowed_origins` defaults to `http://localhost:3000,http://localhost:3001`, identical to current behaviour.

3. **`ci.yml` triggers on PR:** Open a test PR → confirm only `ci.yml` runs (not `deploy.yml`).

4. **`deploy.yml` triggers on merge:** Merge a test PR to master → confirm E2E → ECR push (both tags present) → GitOps commit → no SAST re-run.

5. **`promote-prod.yml` approval gate:** Trigger `workflow_dispatch` → confirm workflow pauses at `environment: production` job until a required reviewer approves in the GitHub UI.

6. **E2E suite:** `bash test_e2e.sh` → 42/42 passed.
