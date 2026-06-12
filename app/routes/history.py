import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.persistence import list_history, get_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/history", response_class=JSONResponse)
async def history(limit: int = 30):
    """历史记录列表"""
    try:
        return JSONResponse(content={"history": list_history(limit)})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/history/{record_id}", response_class=JSONResponse)
async def history_detail(record_id: int):
    """加载历史记录"""
    try:
        result = get_analysis(record_id)
        if result is None:
            return JSONResponse(content={"error": "记录不存在"}, status_code=404)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
