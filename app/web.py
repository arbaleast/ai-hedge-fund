"""AI 基金分析 Web UI — 现代化界面 (P0-3 + 持久化)"""
import logging
import sys
from fastapi import FastAPI

from app.routes import ui, analyze, history, favorites

# ===== 日志配置 — 关键：stderr 输出到 docker logs =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger("ai_fund.web")
logger.setLevel(logging.INFO)

app = FastAPI(title="AI 基金分析")

app.include_router(ui.router)
app.include_router(analyze.router)
app.include_router(history.router)
app.include_router(favorites.router)
