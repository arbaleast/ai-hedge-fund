"""GET/POST/PUT/DELETE /api/favorites — 持仓 CRUD + metrics"""
import asyncio
import logging

from fastapi import APIRouter, Form, HTTPException

from app.persistence import list_favorites, add_favorite, put_favorite, remove_favorite
from app.services.quotes import get_favorite_with_metrics, _date_to_ts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/favorites")
async def favorites_list() -> list:
    """返回所有 favorites + 实时 metrics. 单只失败仅影响该行 status, 不整体 500."""
    raw = list_favorites()
    results: list[dict] = []
    for fav in raw:
        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, fav["code"])
            if m:
                results.append(m.__dict__)
            else:
                results.append({"code": fav["code"], "status": "error"})
        except Exception:
            logger.exception("Failed to get metrics for %s", fav["code"])
            results.append({"code": fav["code"], "status": "error"})
    return results


@router.post("/favorites", status_code=201)
async def favorites_add(
    code: str = Form(...),
    name: str = Form(...),
    buy_price: float = Form(...),
    buy_amount: float = Form(...),
    buy_date: str = Form(...),
    note: str = Form(""),
) -> dict:
    """5 字段必填. 校验日期格式, 价格/数量正数, code 长度."""
    if len(code) < 1 or len(code) > 6:
        raise HTTPException(422, detail={"field": "code", "msg": "长度 1-6 位"})
    if _date_to_ts(buy_date) == 0:
        raise HTTPException(422, detail={"field": "buy_date", "msg": "必须是 YYYY-MM-DD 格式"})
    if buy_price <= 0:
        raise HTTPException(422, detail={"field": "buy_price", "msg": "必须为正数"})
    if buy_amount <= 0:
        raise HTTPException(422, detail={"field": "buy_amount", "msg": "必须为正数"})
    add_favorite(code, name, float(buy_price), float(buy_amount), buy_date, note)
    return {"ok": True}


@router.put("/favorites/{code}")
async def favorites_update(
    code: str,
    name: str | None = Form(None),
    buy_price: float | None = Form(None),
    buy_amount: float | None = Form(None),
    buy_date: str | None = Form(None),
    note: str | None = Form(None),
) -> dict:
    """部分字段更新. 全 None 返 422."""
    if all(v is None for v in (name, buy_price, buy_amount, buy_date, note)):
        raise HTTPException(422, detail={"msg": "至少提供一个更新字段"})
    put_favorite(code, name, buy_price, buy_amount, buy_date, note)
    return {"ok": True}


@router.delete("/favorites/{code}")
async def favorites_remove(code: str) -> dict:
    remove_favorite(code)
    return {"ok": True}
