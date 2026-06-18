#!/usr/bin/env bash
# Quick CLI to start an Alpha Shoop agent run.
# Usage: ./run.sh "your task description" [max_budget_usd]
# Example: ./run.sh "Find trending electronics under $50 with 30% margin" 100

set -euo pipefail

API="http://localhost:8000/api/v1"
TASK="${1:-Build a store for trending home decor products under \$50}"
BUDGET="${2:-100}"

# Get a fresh token
TOKEN=$(curl -sf -X POST "$API/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"operator":"dev-operator"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:30}..."

# Start the run
RESPONSE=$(curl -sf -X POST "$API/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"task\":\"$TASK\",\"max_budget_usd\":$BUDGET}")

THREAD=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['thread_id'])")
echo "Started: $THREAD"
echo "Watch: http://localhost:3000 → Live Runs"

# Poll status
while true; do
  STATUS=$(curl -sf "$API/status/$THREAD" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], '| node:', d.get('current_node',''))")
  echo "  $STATUS"
  if [[ "$STATUS" == completed* || "$STATUS" == failed* || "$STATUS" == killed* ]]; then
    break
  fi
  sleep 3
done
