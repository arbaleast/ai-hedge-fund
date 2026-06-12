#!/usr/bin/env bash
# SCENARIO: S2 - 添加基金（5 字段）
# GIVEN: 数据库为空
# WHEN: POST /api/favorites 携带 5 个必填字段 (code, name, buy_price, buy_amount, buy_date)
# THEN: 返回 201, 之后 GET /api/favorites 应包含该项, 且返回的字段值与提交的一致

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s2_XXXX.db)
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

# POST 添加基金
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/favorites" \
    -d "code=000001" \
    -d "name=测试基金A" \
    -d "buy_price=1.5" \
    -d "buy_amount=10000" \
    -d "buy_date=2024-01-15")
http_code=$(echo "$response" | tail -1)

if [ "$http_code" != "201" ]; then
    echo "FAIL: expected HTTP 201, got $http_code" >&2
    exit 1
fi

# GET 验证列表包含该项
list=$(curl -s "$BASE/api/favorites")
echo "$list" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not isinstance(data, list):
    print('FAIL: expected list response', file=sys.stderr)
    sys.exit(1)
found = [f for f in data if f.get('code') == '000001']
if not found:
    print('FAIL: item with code=000001 not found in list', file=sys.stderr)
    sys.exit(1)
item = found[0]
for key in ['code', 'name', 'buy_price', 'buy_amount', 'buy_date']:
    if key not in item:
        print(f'FAIL: missing key {key} in item', file=sys.stderr)
        sys.exit(1)
if item.get('code') != '000001':
    print(f'FAIL: code mismatch', file=sys.stderr)
    sys.exit(1)
print('OK')
"

echo "PASS: S2 - 添加基金（5 字段）"
