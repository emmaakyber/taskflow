#!/usr/bin/env bash
# End-to-end smoke test against a running stack. Runs the exact sample calls
# from the brief and asserts on the responses. Usage: ./scripts/smoke.sh [base_url]
set -euo pipefail

BASE="${1:-http://localhost:5000}"
PASS=0; FAIL=0

check() {  # check <description> <expected_substring> <actual>
  if [[ "$3" == *"$2"* ]]; then echo "  ok   $1"; PASS=$((PASS+1));
  else echo "  FAIL $1"; echo "       expected to contain: $2"; echo "       got: $3"; FAIL=$((FAIL+1)); fi
}

echo "Smoke test against $BASE"

echo "waiting for /health ..."
for _ in $(seq 1 30); do
  curl -sf "$BASE/health" > /dev/null && break
  sleep 1
done

# Start from a known state: delete anything already there.
for id in $(curl -s "$BASE/tasks" | python3 -c 'import json,sys; print(" ".join(str(t["id"]) for t in json.load(sys.stdin)))'); do
  curl -s -X DELETE "$BASE/tasks/$id" > /dev/null
done

echo "sample API usage from the brief:"
CREATE=$(curl -s -X POST "$BASE/tasks" -H "Content-Type: application/json" -d '{"title": "Write report"}')
check "POST /tasks creates a task" '"title":"Write report"' "$(echo "$CREATE" | tr -d '\n')"
ID=$(echo "$CREATE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

LIST=$(curl -s "$BASE/tasks")
check "GET /tasks lists it" "\"id\":$ID" "$(echo "$LIST" | tr -d '\n')"

COMPLETE=$(curl -s -X PUT "$BASE/tasks/$ID/complete")
check "PUT /tasks/$ID/complete marks completed" '"completed":true' "$(echo "$COMPLETE" | tr -d '\n')"

STATS=$(curl -s "$BASE/tasks/stats")
check "GET /tasks/stats counts 1 total, 1 completed" '"total":1,"completed":1,"pending":0' "$(echo "$STATS" | tr -d '\n')"

DEL=$(curl -s -X DELETE "$BASE/tasks/$ID")
check "DELETE /tasks/$ID confirms deletion" '"deleted":true' "$(echo "$DEL" | tr -d '\n')"

echo "error handling:"
NF=$(curl -s -w " %{http_code}" -X PUT "$BASE/tasks/$ID/complete")
check "completing a deleted task is a JSON 404" '"code":"not_found"' "$(echo "$NF" | tr -d '\n')"
check "...with status 404" "404" "$NF"

BAD=$(curl -s -w " %{http_code}" -X POST "$BASE/tasks" -H "Content-Type: application/json" -d '{"title": ""}')
check "empty title is a 400 validation error" '"code":"validation_error"' "$(echo "$BAD" | tr -d '\n')"

NOJSON=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/tasks" -d 'title=x')
check "non-JSON body is a 415" "415" "$NOJSON"

echo
echo "$PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
