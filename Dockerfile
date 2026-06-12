FROM python:3.11-slim

WORKDIR /app

# 只复制依赖清单和源码（跳过原版 langchain 和旧 agent 文件）
COPY pyproject.toml ./
COPY src/ ./src/
COPY app/ ./app/

# 安装最小依赖集
RUN pip install --no-cache-dir \
    pydantic \
    python-dotenv \
    pandas \
    numpy \
    httpx \
    rich \
    colorama \
    tabulate \
    matplotlib \
    fastapi \
    uvicorn \
    python-multipart \
    langgraph \
    backtrader \
    && rm -rf /root/.cache/pip

ENV PYTHONPATH=/app

# 数据持久化目录
VOLUME ["/data"]
ENV AI_FUND_DB=/data/ai_fund.db

# 默认启动 Web UI (端口 8080)
# CLI 用法: docker run --rm ai-fund:latest python3 src/main.py --codes 019305
CMD ["python3", "-m", "uvicorn", "app.web:app", "--host", "0.0.0.0", "--port", "8080"]
