#!/usr/bin/env bash
# SCENARIO: S4 - 列表含 metrics 字段
# GIVEN: 数据库至少含一条完整记录 (code=000001)
# WHEN: GET /api/favorites
# THEN: 返回 status=200, 每项含 9 个 metrics 字段
#        (code/name/buy_price/buy_amount/buy_date/current_nav/current_value/return_pct/max_drawdown) + status

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s4_XXXX.db)
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

# 先添加一条记录 (确保列表非空)
curl -s -X POST "$BASE/api/favorites" \
    -d "code=000001" \
    -d "name=测试基金A" \
    -d "buy_price=1.5" \
    -d "buy_amount=10000" \
    -d "buy_date=2024-01-15" > /dev/null

# GET 列表
list=$(curl -s "$BASE/api/favorites")

echo "$list" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not isinstance(data, list) or len(data) == 0:
    print('FAIL: expected non-empty list', file=sys.stderr)
    sys.exit(1)
required = [
    'code', 'name', 'buy_price', 'buy_amount', 'buy_date',
    'current_nav', 'current_value', 'return_pct', 'max_drawdown',
    'status'
]
for item in data:
    for key in required:
        if key not in item:
            print(f'FAIL: item {item.get(\"code\",\"??\")} missing key: {key}', file=sys.stderr)
            sys.exit(1)
print('OK')
"

echo "PASS: S4 - 列表含 metrics 字段"
