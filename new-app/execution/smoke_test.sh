#!/bin/bash
# execution/smoke_test.sh
# Runs end-to-end smoke tests against the ORBIT ORC API
#
# Usage: bash execution/smoke_test.sh [API_BASE_URL]
# Default API_BASE_URL is http://localhost:8000
#
# Exits with code 0 if all tests pass, 1 if any fail.

set -e

API="${1:-http://localhost:8000}"
PASS=0
FAIL=0

# ── Helpers ──────────────────────────────────────────────────────────────────

green() { echo -e "\033[0;32m✅ $1\033[0m"; }
red()   { echo -e "\033[0;31m❌ $1\033[0m"; }

check() {
  local label="$1"
  local result="$2"
  local expect="$3"

  if echo "$result" | grep -q "$expect"; then
    green "$label"
    PASS=$((PASS + 1))
  else
    red "$label"
    echo "   Expected to find: $expect"
    echo "   Got: $result"
    FAIL=$((FAIL + 1))
  fi
}

# ── Tests ─────────────────────────────────────────────────────────────────────

echo ""
echo "Running ORBIT smoke tests against: $API"
echo "─────────────────────────────────────────"

# Test 1: Health check
echo ""
echo "Test 1: Health check"
RESULT=$(curl -s -o /dev/null -w "%{http_code}" "$API/health")
check "GET /health returns 200" "$RESULT" "200"

# Test 2: Data-change event (PII scanning)
echo ""
echo "Test 2: Data-change event (PII detection)"
RESULT=$(curl -s -X POST "$API/ingest/data-change" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": [
      "John Doe SSN 123-45-6789 email john@example.com card 4111111111111111"
    ]
  }')

check "data-change returns asset_id" "$RESULT" "corebank-db-01"
check "data-change returns sensitivity score" "$RESULT" "current_sensitivity_score"
check "data-change detects PII types" "$RESULT" "detected_pii_types"

# Test 3: Core alert ingestion
echo ""
echo "Test 3: Core alert → ActionCard creation"
RESULT=$(curl -s -X POST "$API/ingest/core-alert" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "SMOKE-001",
    "summary": "Critical PostgreSQL vulnerability on corebank-db-01",
    "confidence": 0.95,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "CRITICAL", "cve_id": "CVE-2024-99999"}
  }')

check "core-alert returns alert_id or action_id" "$RESULT" "SMOKE"
check "core-alert returns priority" "$RESULT" "priority"
check "core-alert returns status" "$RESULT" "status"

# Test 4: Crown jewels query
echo ""
echo "Test 4: Crown jewels query"
RESULT=$(curl -s "$API/query/crown-jewels")
check "crown-jewels endpoint responds" "$RESULT" "."

# Test 5: High sensitivity query
echo ""
echo "Test 5: High sensitivity query"
RESULT=$(curl -s "$API/query/high-sensitivity")
check "high-sensitivity endpoint responds" "$RESULT" "."

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
echo ""

if [ $FAIL -eq 0 ]; then
  green "All smoke tests passed"
  exit 0
else
  red "$FAIL test(s) failed"
  exit 1
fi
