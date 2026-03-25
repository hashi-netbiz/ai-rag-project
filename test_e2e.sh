#!/usr/bin/env bash
# =============================================================================
# RAG RBAC Chatbot — End-to-End Regression Test Suite
# =============================================================================
# Prerequisites:
#   - Backend running:  cd backend && uv run uvicorn app.main:app --port 8000
#   - Frontend running: cd frontend-next && npm run dev  (port 3001)
#
# Usage:
#   bash test_e2e.sh
#
# Exit code 0 = all tests passed
# Exit code 1 = one or more tests failed
# =============================================================================

BACKEND="http://localhost:8000"
FRONTEND="http://localhost:3001"
PASS=0
FAIL=0

# Colours
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}  PASS${NC}  $1"; ((PASS++)); }
fail() { echo -e "${RED}  FAIL${NC}  $1"; ((FAIL++)); }
section() { echo -e "\n${YELLOW}=== $1 ===${NC}"; }

# Helper — POST JSON, return body
post_json() { curl -s -X POST "$1" -H "Content-Type: application/json" -d "$2"; }

# Helper — assert response contains substring
assert_contains() {
  local label="$1" body="$2" expected="$3"
  if echo "$body" | grep -q "$expected"; then
    pass "$label"
  else
    fail "$label — expected '$expected' in: $(echo "$body" | head -c 120)"
  fi
}

assert_not_contains() {
  local label="$1" body="$2" unexpected="$3"
  if echo "$body" | grep -q "$unexpected"; then
    fail "$label — did NOT expect '$unexpected' in: $(echo "$body" | head -c 120)"
  else
    pass "$label"
  fi
}

assert_http() {
  local label="$1" url="$2" expected_code="$3"
  local actual_code
  actual_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$actual_code" = "$expected_code" ]; then
    pass "$label (HTTP $actual_code)"
  else
    fail "$label — expected HTTP $expected_code, got HTTP $actual_code"
  fi
}

# =============================================================================
section "1. SERVICE HEALTH"
# =============================================================================

assert_http "Backend health endpoint" "$BACKEND/health" "200"
assert_http "Frontend login page" "$FRONTEND" "200"
assert_http "Next.js API proxy reachable" "$FRONTEND/api/auth/login" "405"  # GET → Method Not Allowed means route exists

# =============================================================================
section "2. AUTHENTICATION"
# =============================================================================

# Valid logins — all 6 demo users
for user in alice bob carol dave eve frank; do
  body=$(post_json "$BACKEND/auth/login" "{\"username\":\"$user\",\"password\":\"pass123\"}")
  assert_contains "Login: $user" "$body" "access_token"
done

# Invalid credentials
body=$(post_json "$BACKEND/auth/login" '{"username":"alice","password":"wrongpassword"}')
assert_contains "Login rejects bad password" "$body" "401\|Incorrect\|incorrect\|detail"

# Missing token → 401 on protected endpoint
status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -d '{"query":"test"}')
[ "$status" = "401" ] && pass "No token → 401 on /chat/query" || fail "No token should return 401, got $status"

# Get /auth/me returns correct role
ALICE_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"alice","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
me_body=$(curl -s "$BACKEND/auth/me" -H "Authorization: Bearer $ALICE_TOKEN")
assert_contains "/auth/me returns username" "$me_body" "alice"
assert_contains "/auth/me returns role" "$me_body" "finance"

# =============================================================================
section "3. RBAC ENFORCEMENT — ACCESS DENIED"
# =============================================================================

# employee (frank) cannot see finance data
FRANK_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"frank","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
body=$(post_json "$BACKEND/chat/query" '{"query":"What is our gross margin?"}' | curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $FRANK_TOKEN" -d '{"query":"What is our gross margin?"}')
assert_contains "Employee cannot see finance data" "$body" "don't have access\|do not have access\|I don"

# employee cannot see HR data
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $FRANK_TOKEN" \
  -d '{"query":"What is the salary of Shaurya Joshi?"}')
assert_contains "Employee cannot see HR salary data" "$body" "don't have access\|do not have access\|I don"

# employee cannot see engineering data
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $FRANK_TOKEN" \
  -d '{"query":"What is the system architecture?"}')
assert_contains "Employee cannot see engineering data" "$body" "don't have access\|do not have access\|I don"

# finance (alice) cannot see HR data
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"query":"What is the performance rating of FINEMP1001?"}')
assert_contains "Finance cannot see HR data" "$body" "don't have access\|do not have access\|I don"

# finance (alice) cannot see marketing data
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"query":"What was the Return on Ad Spend for digital campaigns?"}')
assert_contains "Finance cannot see marketing data" "$body" "don't have access\|do not have access\|I don"

# =============================================================================
section "4. RBAC ENFORCEMENT — ACCESS GRANTED"
# =============================================================================

# finance (alice) can see finance data
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"query":"What is our gross margin?"}')
assert_not_contains "Finance can see finance data" "$body" "don't have access"
assert_contains "Finance answer contains sources" "$body" "sources"

# engineering (dave) can see engineering data
DAVE_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"dave","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DAVE_TOKEN" \
  -d '{"query":"Describe the high-level system architecture"}')
assert_not_contains "Engineering can see engineering data" "$body" "don't have access"
assert_contains "Engineering answer has architecture content" "$body" "microservices\|architecture\|Microservices"

# hr (carol) can see HR data
CAROL_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"carol","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $CAROL_TOKEN" \
  -d '{"query":"What department does Aadhya Patel work in?"}')
assert_not_contains "HR can see HR data" "$body" "don't have access"

# marketing (bob) can see marketing data
BOB_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"bob","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BOB_TOKEN" \
  -d '{"query":"What is the total marketing budget?"}')
assert_not_contains "Marketing can see marketing data" "$body" "don't have access"

# c_level (eve) can see all data
EVE_TOKEN=$(post_json "$BACKEND/auth/login" '{"username":"eve","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
for query in "What is our gross margin?" "What is the total marketing budget?" "What is the system architecture?"; do
  body=$(curl -s -X POST "$BACKEND/chat/query" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $EVE_TOKEN" \
    -d "{\"query\":\"$query\"}")
  assert_not_contains "C-level can query: $query" "$body" "don't have access"
done

# All roles can see general/employee handbook data
for token_var in ALICE_TOKEN BOB_TOKEN CAROL_TOKEN DAVE_TOKEN EVE_TOKEN FRANK_TOKEN; do
  eval "token=\$$token_var"
  body=$(curl -s -X POST "$BACKEND/chat/query" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $token" \
    -d '{"query":"What is the annual leave entitlement?"}')
  assert_not_contains "All roles can see general docs ($token_var)" "$body" "don't have access"
done

# =============================================================================
section "5. SOURCE CITATIONS"
# =============================================================================

body=$(curl -s -X POST "$BACKEND/chat/query" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"query":"What is our gross margin?"}')
assert_contains "Response includes sources array" "$body" '"sources"'
assert_contains "Sources contain file field" "$body" '"file"'
assert_contains "Sources contain section field" "$body" '"section"'

# =============================================================================
section "6. NEXT.JS API PROXIES"
# =============================================================================

# Login proxy
body=$(post_json "$FRONTEND/api/auth/login" '{"username":"alice","password":"pass123"}')
assert_contains "Next.js login proxy works" "$body" "access_token"
assert_contains "Next.js login proxy returns role" "$body" "finance"

# Chat query proxy
PROXY_TOKEN=$(post_json "$FRONTEND/api/auth/login" '{"username":"alice","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
body=$(curl -s -X POST "$FRONTEND/api/chat/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PROXY_TOKEN" \
  -d '{"query":"What is our gross margin?"}')
assert_contains "Next.js chat proxy returns answer" "$body" "answer"
assert_not_contains "Next.js chat proxy not blocked" "$body" "don't have access"

# Auth/me proxy
body=$(curl -s "$FRONTEND/api/auth/me" -H "Authorization: Bearer $PROXY_TOKEN")
assert_contains "Next.js /auth/me proxy works" "$body" "alice"

# =============================================================================
section "7. TYPESCRIPT (frontend-next)"
# =============================================================================

cd frontend-next 2>/dev/null || { fail "frontend-next directory not found"; }
tsc_output=$(npm run type-check 2>&1)
if echo "$tsc_output" | grep -q "error TS"; then
  fail "TypeScript check — errors found:\n$tsc_output"
else
  pass "TypeScript check — 0 errors"
fi
cd ..

# =============================================================================
section "RESULTS"
# =============================================================================

TOTAL=$((PASS + FAIL))
echo ""
echo -e "Passed: ${GREEN}$PASS${NC} / $TOTAL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failed: ${RED}$FAIL${NC} / $TOTAL"
  echo ""
  echo "One or more tests failed. Check output above for details."
  exit 1
else
  echo -e "${GREEN}All $TOTAL tests passed.${NC}"
  exit 0
fi
