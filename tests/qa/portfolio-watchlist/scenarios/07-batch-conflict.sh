#!/usr/bin/env bash
# SCENARIO: S7 - 并发冲突
# GIVEN: 数据库至少一条记录 (使 SSE 需要网络 I/O, 不会瞬间完成)
# WHEN: 第一个 SSE 客户端连接后, 1s 后再起第二个并发连接
# THEN: 第二个返回 status=409 (refresh already running)

set -euo pipefail

PORT="${PORT:-8765}"
BASE="http://localhost:$PORT"

# 使用临时文件确保每个连接共享同一 DB (AI_FUND_DB=:memory: 会为每个连接创建独立实例)
TEST_DB=$(mktemp /tmp/ai_fund_s7_XXXX.db)
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

# 添加 15 条记录 → SSE 处理需要 ~3s, 确保 1s 后仍在运行
for code in 000001 000002 000003 161725 110011 005827 260108 008888 110022 007777 006666 005555 004444 003333 002222; do
    curl -s -X POST "$BASE/api/favorites" \
        -d "code=$code" \
        -d "name=基金$code" \
        -d "buy_price=1.5" \
        -d "buy_amount=10000" \
        -d "buy_date=2024-01-15" > /dev/null
done

# 启动后台 SSE client (保持连接)
curl -s -N --max-time 30 "$BASE/api/favorites/refresh" > /tmp/sse_out_$$.txt 2>&1 &
SSE_PID=$!

# 等待第一个 client 建立连接并开始处理
sleep 1

# 第二个 client → 应被拒绝 (409)
second_resp=$(curl -s -w "\n%{http_code}" --max-time 5 "$BASE/api/favorites/refresh")
second_http=$(echo "$second_resp" | tail -1)

# 清理后台 SSE
kill "$SSE_PID" 2>/dev/null || true
rm -f /tmp/sse_out_$$.txt

if [ "$second_http" != "409" ]; then
    echo "FAIL: second SSE client expected 409, got $second_http" >&2
    exit 1
fi

echo "PASS: S7 - 并发冲突"
