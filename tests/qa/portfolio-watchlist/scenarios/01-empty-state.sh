#!/usr/bin/env bash
# SCENARIO: S1 - 空状态
# GIVEN: 数据库为空（使用 AI_FUND_DB=:memory: 强制空数据库）
# WHEN: 调用 GET /api/favorites
# THEN: 返回 status=200, body=[] (空数组)

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s1_XXXX.db)
trap 'rm -f "$TEST_DB"; kill "$UVICORN_PID" 2>/dev/null || true' EXIT

AI_FUND_DB="$TEST_DB" uvicorn app.web:app --port "$PORT" --log-level warning > /dev/null 2>&1 &
UVICORN_PID=$!

# 等待 server 就绪
for i in $(seq 1 15); do
    if curl -s -o /dev/null "$BASE/api/favorites" 2>/dev/null; then
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "FAIL: server did not start in time" >&2
        exit 1
    fi
    sleep 1
done

# S1: GET /api/favorites → 空数组
response=$(curl -s -w "\n%{http_code}" "$BASE/api/favorites")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" != "200" ]; then
    echo "FAIL: expected HTTP 200, got $http_code" >&2
    exit 1
fi

# 验证 body 为空数组
if ! echo "$body" | python3 -c "import json,sys; data=json.load(sys.stdin); assert isinstance(data, list) and len(data) == 0, f'expected empty list, got {data}'" 2>/dev/null; then
    echo "FAIL: body is not empty array: $body" >&2
    exit 1
fi

echo "PASS: S1 - 空状态"
