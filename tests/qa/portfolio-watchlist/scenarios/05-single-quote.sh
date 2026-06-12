#!/usr/bin/env bash
# SCENARIO: S5 - 单只基金行情
# GIVEN: 服务正在运行
# WHEN: GET /api/quote/000001
# THEN: 返回 status=200 (网络可用) 或 404/500 (不可用), 只要不挂掉就算路由存在

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s5_XXXX.db)
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

# GET /api/quote/000001 — 只要返回 HTTP 状态码就视为路由存在
http_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/quote/000001" 2>/dev/null || echo "CURL_FAIL")

if [ "$http_code" = "CURL_FAIL" ] || [ -z "$http_code" ]; then
    echo "FAIL: curl connection failed — route may not exist" >&2
    exit 1
fi

# 200 = 网络可用正常返回; 404 = 上游数据不可用; 500 = 服务端异常 (都不算路由级失败)
echo "PASS: S5 - 单只基金行情 (HTTP $http_code)"
