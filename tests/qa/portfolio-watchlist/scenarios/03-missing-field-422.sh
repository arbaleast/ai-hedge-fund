#!/usr/bin/env bash
# SCENARIO: S3 - 缺字段返回 422
# GIVEN: 任意数据库状态
# WHEN: POST /api/favorites 缺 buy_date 字段
# THEN: 返回 status=422, JSON detail 包含 "buy_date"

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s3_XXXX.db)
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

# POST 缺 buy_date
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/favorites" \
    -d "code=000002" \
    -d "name=测试基金B" \
    -d "buy_price=2.0" \
    -d "buy_amount=5000")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" != "422" ]; then
    echo "FAIL: expected HTTP 422, got $http_code" >&2
    exit 1
fi

# 验证 body detail 包含 "buy_date"
echo "$body" | python3 -c "
import json, sys
data = json.load(sys.stdin)
detail = data.get('detail', '')
detail_str = json.dumps(detail, ensure_ascii=False)
if 'buy_date' not in detail_str:
    print(f'FAIL: expected buy_date in detail, got {detail_str}', file=sys.stderr)
    sys.exit(1)
print('OK')
"

echo "PASS: S3 - 缺字段返回 422"
