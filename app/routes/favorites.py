"""GET/POST/DELETE /api/favorites — fund favorites CRUD"""
import logging

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from app.persistence import list_favorites, add_favorite, remove_favorite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/favorites", response_class=JSONResponse)
async def favorites_list():
    try:
        return JSONResponse(content={"favorites": list_favorites()})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/favorites", response_class=JSONResponse)
async def favorites_add(code: str = Form(...), name: str = Form(""), note: str = Form("")):
    try:
        add_favorite(code, name, note)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.delete("/favorites/{code}", response_class=JSONResponse)
async def favorites_remove(code: str):
    try:
        remove_favorite(code)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
