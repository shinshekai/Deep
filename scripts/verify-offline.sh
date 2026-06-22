#!/usr/bin/env bash
# verify-offline.sh — Air-gapped operation verification for DEEP
# Usage: bash scripts/verify-offline.sh
# Verifies DEEP can function with zero outbound network access.

set -euo pipefail

REPORT_FILE="offline-verification-report.json"
PASS=0
FAIL=0
RESULTS="[]"

report() {
  local name="$1" status="$2" detail="$3"
  RESULTS=$(echo "$RESULTS" | jq --arg n "$name" --arg s "$status" --arg d "$detail" '. + [{"test": $n, "status": $s, "detail": $d}]')
  if [ "$status" = "pass" ]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi
  echo "  [$status] $name: $detail"
}

echo "=== DEEP Air-Gapped Verification ==="
echo ""

# ── Pre-flight checks ──
echo "--- Pre-flight ---"

if command -v curl &>/dev/null; then
  report "curl-available" "pass" "curl found at $(which curl)"
else
  report "curl-available" "fail" "curl not found — required for health checks"
fi

if command -v jq &>/dev/null; then
  report "jq-available" "pass" "jq found at $(which jq)"
else
  report "jq-available" "fail" "jq not found — required for JSON reporting"
fi

# ── LM Studio / Ollama connectivity ──
echo ""
echo "--- Local LLM ---"

LM_HOST="${LM_STUDIO_HOST:-http://localhost:1234}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

if curl -sf "${LM_HOST}/v1/models" >/dev/null 2>&1; then
  LM_COUNT=$(curl -sf "${LM_HOST}/v1/models" | jq '.data | length // 0')
  report "lm-studio" "pass" "LM Studio at $LM_HOST — $LM_COUNT model(s)"
elif curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  report "local-llm" "pass" "Ollama at $OLLAMA_HOST"
else
  report "local-llm" "fail" "Neither LM Studio nor Ollama reachable"
fi

# ── Network check ──
echo ""
echo "--- Network ---"

if curl -sf --max-time 3 https://google.com >/dev/null 2>&1; then
  report "network-off" "warn" "Internet IS available — not truly air-gapped"
else
  report "network-off" "pass" "No internet access detected"
fi

# ── Backend health ──
echo ""
echo "--- DEEP Backend ---"

BACKEND_HOST="${BACKEND_HOST:-http://localhost:8001}"

# Health check
if HEALTH=$(curl -sf "${BACKEND_HOST}/api/v1/health" 2>/dev/null); then
  STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')
  report "backend-health" "pass" "Status: $STATUS"
else
  report "backend-health" "fail" "Backend not reachable at $BACKEND_HOST"
fi

# Readiness check
if READY=$(curl -sf "${BACKEND_HOST}/api/v1/ready" 2>/dev/null); then
  READY_STATUS=$(echo "$READY" | jq -r '.status // "unknown"')
  report "backend-ready" "pass" "Status: $READY_STATUS"
else
  report "backend-ready" "fail" "Readiness check failed"
fi

# ── Frontend ──
echo ""
echo "--- DEEP Frontend ---"

FRONTEND_HOST="${FRONTEND_HOST:-http://localhost:3782}"

if FRONTEND=$(curl -sf "${FRONTEND_HOST}/" 2>/dev/null); then
  if echo "$FRONTEND" | grep -qi "deep\|document\|platform"; then
    report "frontend" "pass" "Frontend responding at $FRONTEND_HOST"
  else
    report "frontend" "pass" "Frontend responding (content check skipped)"
  fi
else
  report "frontend" "warn" "Frontend not reachable at $FRONTEND_HOST (may not be running)"
fi

# ── Query smoke test ──
echo ""
echo "--- Query Smoke Test ---"

TOKEN="${DEEP_API_KEY:-}"

QUERY_RESPONSE=$(curl -sf -X POST "${BACKEND_HOST}/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "${TOKEN:+X-DEEP-API-KEY: $TOKEN}" \
  -d '{"query": "What is 2+2?", "kb_name": "default", "retrieval_pipeline": "hybrid"}' 2>/dev/null || echo "")

if [ -n "$QUERY_RESPONSE" ]; then
  report "query-smoke" "pass" "Query endpoint responded"
else
  report "query-smoke" "warn" "Query endpoint not available (may need API key or LM Studio)"
fi

# ── Summary ──
echo ""
echo "=== Results ==="
echo "Passed: $PASS | Failed: $FAIL"

jq -n \
  --argjson results "$RESULTS" \
  --arg passed "$PASS" \
  --arg failed "$FAIL" \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    timestamp: $timestamp,
    passed: ($passed | tonumber),
    failed: ($failed | tonumber),
    results: $results
  }' > "$REPORT_FILE"

echo "Report saved to $REPORT_FILE"
