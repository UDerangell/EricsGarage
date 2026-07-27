#!/usr/bin/env bash
#
# Exercises the zzStructure POC API against the test plan in §9 of
# zzstructure-poc-spec.md. Requires: the server already running (see
# README.md), curl, and python3 (used instead of jq so this script doesn't
# require an extra system package).
#
# Usage:
#   ./scripts/run-tests.sh [base_url]
#
# Exit code is 0 if every test passed, 1 otherwise.

set -u

BASE_URL="${1:-http://localhost:3000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTH_FILE="$SCRIPT_DIR/../data/authorization.json"

ALICE=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['users'][0]['id'])")
BOB=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['users'][1]['id'])")

PASS_COUNT=0
FAIL_COUNT=0

# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

# jget <json> <python-expr-on-d>  — e.g. jget "$BODY" "d['cellId']"
jget() {
  python3 -c "
import json, sys
d = json.loads(sys.argv[1]) if sys.argv[1].strip() else None
try:
    print($2)
except Exception:
    print('__JGET_ERROR__')
" "$1"
}

# request METHOD PATH BEARER [JSON_BODY]
# Sets globals: STATUS, BODY
request() {
  local method="$1" path="$2" bearer="$3" body="${4:-}"
  local tmp
  tmp=$(mktemp)
  local args=(-s -o "$tmp" -w '%{http_code}' -X "$method" "${BASE_URL}${path}")
  if [ -n "$bearer" ]; then
    args+=(-H "Authorization: Bearer $bearer")
  fi
  if [ -n "$body" ]; then
    args+=(-H "Content-Type: application/json" -d "$body")
  fi
  STATUS=$(curl "${args[@]}")
  BODY=$(cat "$tmp")
  rm -f "$tmp"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '  \033[32mPASS\033[0m %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '  \033[31mFAIL\033[0m %s\n' "$1"
  printf '       expected: %s\n' "$2"
  printf '       actual:   %s\n' "$3"
}

# check_status <label> <expected_status>
check_status() {
  local label="$1" expected="$2"
  if [ "$STATUS" = "$expected" ]; then
    pass "$label (status $STATUS)"
  else
    fail "$label" "status $expected" "status $STATUS, body=$BODY"
  fi
}

# check_status_and_error <label> <expected_status> <expected_error_code>
check_status_and_error() {
  local label="$1" expected_status="$2" expected_error="$3"
  local actual_error
  actual_error=$(jget "$BODY" "d.get('error')")
  if [ "$STATUS" = "$expected_status" ] && [ "$actual_error" = "$expected_error" ]; then
    pass "$label"
  else
    fail "$label" "status $expected_status, error=$expected_error" "status $STATUS, body=$BODY"
  fi
}

section() {
  printf '\n\033[1m%s\033[0m\n' "$1"
}

# ---------------------------------------------------------------------------
# TC-01 / TC-02 — auth failures
# ---------------------------------------------------------------------------
section "Auth"

request GET "/structures/$ALICE/dimensions" ""
check_status_and_error "TC-01 missing auth header -> 401" 401 unauthorized

request GET "/structures/$ALICE/dimensions" "99999999-9999-7999-8999-999999999999"
check_status_and_error "TC-02 unknown bearer uuid -> 401" 401 unauthorized

# ---------------------------------------------------------------------------
# TC-03 — read own dimensions (7 system dimensions after bootstrap)
# ---------------------------------------------------------------------------
section "Bootstrap sanity"

request GET "/structures/$ALICE/dimensions" "$ALICE"
DIM_COUNT=$(jget "$BODY" "len(d['dimensions'])")
if [ "$STATUS" = "200" ] && [ "$DIM_COUNT" = "7" ]; then
  pass "TC-03 Alice has 7 system dimensions after bootstrap"
else
  fail "TC-03 Alice has 7 system dimensions after bootstrap" "status 200, 7 dimensions" "status $STATUS, count=$DIM_COUNT"
fi

request GET "/structures/$BOB/dimensions" "$BOB"
DIM_COUNT_BOB=$(jget "$BODY" "len(d['dimensions'])")
if [ "$STATUS" = "200" ] && [ "$DIM_COUNT_BOB" = "7" ]; then
  pass "Bob has 7 system dimensions after bootstrap"
else
  fail "Bob has 7 system dimensions after bootstrap" "status 200, 7 dimensions" "status $STATUS, count=$DIM_COUNT_BOB"
fi

# ---------------------------------------------------------------------------
# TC-04 — cross-user read
# ---------------------------------------------------------------------------
section "Cross-user reads"

request GET "/structures/$BOB/dimensions" "$ALICE"
check_status "TC-04 Alice reads Bob's dimensions" 200

request GET "/structures/99999999-9999-7999-8999-999999999999/dimensions" "$ALICE"
check_status_and_error "TC-27 unknown structure id -> 404" 404 unknown_structure

# ---------------------------------------------------------------------------
# TC-05..TC-11 — Alice builds her own content
# ---------------------------------------------------------------------------
section "Alice: documents, dimensions, links, Restriction R"

request POST "/structures/$ALICE/documents" "$ALICE" '{"documentId":"alice/2024-01-01-morning-pages.md"}'
DOC_A=$(jget "$BODY" "d['cellId']")
REV=$(jget "$BODY" "d['revision']")
if [ "$STATUS" = "200" ] && [ "$(jget "$BODY" "d['created']")" = "True" ]; then
  pass "TC-05 Alice creates her first document cell (revision=$REV)"
else
  fail "TC-05 Alice creates her first document cell" "200, created=true" "status $STATUS, body=$BODY"
fi

request POST "/structures/$ALICE/dimensions" "$ALICE" '{"name":"journal","namespace":"user"}'
DIM_JOURNAL=$(jget "$BODY" "d['dimension']['id']")
QNAME=$(jget "$BODY" "d['dimension']['qualifiedName']")
if [ "$STATUS" = "200" ] && [ "$QNAME" = "user.journal" ]; then
  pass "TC-06 Alice creates dimension user.journal"
else
  fail "TC-06 Alice creates dimension user.journal" "200, qualifiedName=user.journal" "status $STATUS, body=$BODY"
fi

request POST "/structures/$ALICE/documents" "$ALICE" '{"documentId":"alice/2024-01-08-morning-pages.md"}'
DOC_B=$(jget "$BODY" "d['cellId']")
check_status "TC-07 Alice creates a second document cell" 200

request POST "/structures/$ALICE/links" "$ALICE" "{\"a\":\"$DOC_A\",\"b\":\"$DOC_B\",\"dimension\":\"$DIM_JOURNAL\"}"
check_status "TC-08 Alice links her two entries along user.journal" 200

request POST "/structures/$ALICE/dimensions" "$ALICE" '{"name":"journal","namespace":"user"}'
check_status_and_error "TC-09 duplicate dimension name rejected -> 409" 409 duplicate_dimension

request POST "/structures/$ALICE/links" "$ALICE" "{\"a\":\"$DOC_A\",\"b\":\"$DOC_A\",\"dimension\":\"$DIM_JOURNAL\"}"
check_status_and_error "TC-10 self-link forbidden -> 400" 400 self_link_forbidden

request POST "/structures/$ALICE/documents" "$ALICE" '{"documentId":"alice/2024-01-15-morning-pages.md"}'
DOC_C=$(jget "$BODY" "d['cellId']")

request POST "/structures/$ALICE/links" "$ALICE" "{\"a\":\"$DOC_A\",\"b\":\"$DOC_C\",\"dimension\":\"$DIM_JOURNAL\"}"
check_status_and_error "TC-11 Restriction R violation -> 409" 409 restriction_r_violation

# ---------------------------------------------------------------------------
# TC-12..TC-14 — Bob builds his own content, single-writer enforcement
# ---------------------------------------------------------------------------
section "Bob: documents, dimensions, single-writer enforcement"

request POST "/structures/$BOB/documents" "$BOB" '{"documentId":"bob/reading-list.md"}'
DOC_C_BOB=$(jget "$BODY" "d['cellId']")
check_status "TC-12 Bob creates his document cell" 200

request POST "/structures/$BOB/dimensions" "$BOB" '{"name":"notes","namespace":"user"}'
check_status "TC-13 Bob creates his own dimension" 200

request POST "/structures/$ALICE/links" "$BOB" "{\"a\":\"$DOC_A\",\"b\":\"$DOC_B\",\"dimension\":\"$DIM_JOURNAL\"}"
check_status_and_error "TC-14 cross-user write forbidden -> 403" 403 forbidden

# ---------------------------------------------------------------------------
# TC-15..TC-20 — cross-user read, import, link, view isolation
# ---------------------------------------------------------------------------
section "Cross-user linking and view isolation"

request GET "/structures/$ALICE/cells/$DOC_A" "$BOB"
OWNER_OF_DOC_A=$(jget "$BODY" "d['cell']['ownerId']")
if [ "$STATUS" = "200" ] && [ "$OWNER_OF_DOC_A" = "$ALICE" ]; then
  pass "TC-15 Bob reads one of Alice's cells"
else
  fail "TC-15 Bob reads one of Alice's cells" "200, ownerId=$ALICE" "status $STATUS, body=$BODY"
fi

request POST "/structures/$BOB/foreign-cells" "$BOB" "{\"foreignCellId\":\"$DOC_A\",\"ownerId\":\"$ALICE\"}"
IMPORTED_OWNER=$(jget "$BODY" "d['cell']['ownerId']")
if [ "$STATUS" = "200" ] && [ "$IMPORTED_OWNER" = "$ALICE" ]; then
  pass "TC-16 Bob imports Alice's cell into his own cache"
else
  fail "TC-16 Bob imports Alice's cell into his own cache" "200, ownerId=$ALICE" "status $STATUS, body=$BODY"
fi
ALICE_JSON_BEFORE=$(cat "$SCRIPT_DIR/../data/alice.json")

request POST "/structures/$BOB/dimensions" "$BOB" '{"name":"related-reading","namespace":"user"}'
DIM_RELATED=$(jget "$BODY" "d['dimension']['id']")
check_status "TC-17 Bob creates a dimension to relate to it" 200

request POST "/structures/$BOB/links" "$BOB" "{\"a\":\"$DOC_C_BOB\",\"b\":\"$DOC_A\",\"dimension\":\"$DIM_RELATED\"}"
check_status "TC-18 Bob links his cell to Alice's imported cell" 200

ALICE_JSON_AFTER=$(cat "$SCRIPT_DIR/../data/alice.json")
if [ "$ALICE_JSON_BEFORE" = "$ALICE_JSON_AFTER" ]; then
  pass "TC-18b alice.json byte-for-byte unchanged by Bob's link"
else
  fail "TC-18b alice.json byte-for-byte unchanged by Bob's link" "no change" "alice.json changed"
fi

request GET "/structures/$BOB/view?accursed=$DOC_C_BOB&view=h-view&x=$DIM_RELATED&y=00000000-0000-7000-8000-00000000D005" "$BOB"
HAS_ALICE_CELL=$(jget "$BODY" "'$DOC_A' in d['cells']")
if [ "$STATUS" = "200" ] && [ "$HAS_ALICE_CELL" = "True" ]; then
  pass "TC-19 Bob's view includes Alice's imported cell, tagged foreign"
else
  fail "TC-19 Bob's view includes Alice's imported cell, tagged foreign" "200, cell present" "status $STATUS, body=$BODY"
fi

request GET "/structures/$ALICE/view?accursed=$DOC_A&view=h-view&x=$DIM_JOURNAL&y=00000000-0000-7000-8000-00000000D005" "$ALICE"
HAS_BOB_TRACE=$(jget "$BODY" "'$DOC_C_BOB' in d['cells']")
if [ "$STATUS" = "200" ] && [ "$HAS_BOB_TRACE" = "False" ]; then
  pass "TC-20 Alice's own view is unaffected by Bob's link"
else
  fail "TC-20 Alice's own view is unaffected by Bob's link" "200, no trace of Bob" "status $STATUS, body=$BODY"
fi

# ---------------------------------------------------------------------------
# TC-21..TC-22 — unlink
# ---------------------------------------------------------------------------
section "Unlink"

request DELETE "/structures/$BOB/links" "$BOB" "{\"a\":\"$DOC_C_BOB\",\"b\":\"$DOC_A\",\"dimension\":\"$DIM_RELATED\"}"
check_status "TC-21 Bob unlinks the cross-user edge" 200

request DELETE "/structures/$BOB/links" "$BOB" "{\"a\":\"$DOC_C_BOB\",\"b\":\"$DOC_A\",\"dimension\":\"$DIM_RELATED\"}"
check_status_and_error "TC-22 unlinking a non-existent edge -> 404" 404 no_such_connection

# ---------------------------------------------------------------------------
# TC-23..TC-26 — clone, export, optimistic concurrency, missing foreign cell
# ---------------------------------------------------------------------------
section "Clone, export, optimistic concurrency"

request POST "/structures/$ALICE/clones" "$ALICE" "{\"of\":\"$DOC_A\"}"
CLONE_1=$(jget "$BODY" "d['cloneCellId']")
check_status "TC-23 Alice clones a cell" 200

request GET "/structures/$ALICE/export" "$BOB"
EXPORT_REVISION=$(jget "$BODY" "d['revision']")
if [ "$STATUS" = "200" ]; then
  ONDISK_REVISION=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/../data/alice.json'))['revision'])")
  if [ "$EXPORT_REVISION" = "$ONDISK_REVISION" ]; then
    pass "TC-24 export matches the file on disk (revision $EXPORT_REVISION)"
  else
    fail "TC-24 export matches the file on disk" "revision $ONDISK_REVISION" "revision $EXPORT_REVISION"
  fi
else
  fail "TC-24 export matches the file on disk" "status 200" "status $STATUS"
fi

request POST "/structures/$ALICE/links" "$ALICE" "{\"a\":\"$DOC_B\",\"b\":\"$CLONE_1\",\"dimension\":\"$DIM_JOURNAL\",\"expectedRevision\":1}"
check_status_and_error "TC-25 optimistic concurrency conflict -> 409" 409 revision_conflict

request POST "/structures/$BOB/foreign-cells" "$BOB" '{"foreignCellId":"00000000-0000-7000-8000-999999999999","ownerId":"'"$ALICE"'"}'
check_status_and_error "TC-26 importing a non-existent foreign cell -> 404" 404 foreign_cell_not_found

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "-----------------------------------"
echo "Passed: $PASS_COUNT   Failed: $FAIL_COUNT"
echo "-----------------------------------"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
