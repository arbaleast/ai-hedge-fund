#!/usr/bin/env bash
# SCENARIO: S6 - SSE 批量刷新流
# GIVEN: 服务正在运行, favorites 可能为空
# WHEN: GET /api/favorites/refresh
# THEN: 返回 status=200, content-type=text/event-stream, 收到 data: 开头的 SSE 行

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s6_XXXX.db)
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

# 检查 Content-Type 头 (用短超时避免卡住)
content_type=$(curl -s -o /dev/null -w "%{content_type}" --max-time 3 "$BASE/api/favorites/refresh" 2>/dev/null || true)

if [[ "$content_type" != *"text/event-stream"* ]]; then
    echo "FAIL: expected content-type text/event-stream, got '$content_type'" >&2
    exit 1
fi

# 检查 SSE 数据内容 (接收最多 5 秒的流数据)
sse_output=$(curl -s --max-time 5 "$BASE/api/favorites/refresh" 2>/dev/null || true)

if ! echo "$sse_output" | grep -q "^data:"; then
    echo "FAIL: no data: lines received in SSE stream" >&2
    echo "--- raw output ---" >&2
    echo "$sse_output" >&2
    echo "--- end ---" >&2
    exit 1
fi

echo "PASS: S6 - SSE 批量刷新流"
