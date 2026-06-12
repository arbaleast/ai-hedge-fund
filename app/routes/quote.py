"""GET /api/quote/{code} + GET /api/favorites/refresh (SSE)"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.services import quotes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/quote/{code}")
def quote_single(code: str) -> dict:
    """同步 wrapper — 获取单只基金实时行情 (兼容不需要 async 上下文的 client)"""
    quote = asyncio.run(quotes.fetch_quote(code))
    if not quote:
        raise HTTPException(status_code=404, detail="quote not found")
    return asdict(quote)


@router.get("/favorites/refresh")
async def batch_refresh(request: Request) -> Response:
    """SSE 端点 — 批量刷新所有 favorites 的实时行情. 决策: GET (EventSource 限制)."""
    if quotes._refresh_running:
        raise HTTPException(status_code=409, detail="refresh already running")

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in quotes.batch_refresh_quotes():
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
