#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi
export PYTHONPATH="$(pwd)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -z "$AI_FUND_DB" ] && [ ! -d /data ]; then
    mkdir -p "$(pwd)/data"
    export AI_FUND_DB="$(pwd)/data/ai_fund.db"
fi

exec python3 -m uvicorn app.web:app --host "$HOST" --port "$PORT" --no-access-log "$@"
