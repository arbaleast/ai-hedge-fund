"""POST /analyze — fund analysis endpoint"""
import logging

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from app.services.analysis import _run_and_save

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_class=JSONResponse)
async def analyze(
    codes: str = Form(...),
    months: int = Form(24),
    reasoning: str = Form("0"),
    use_llm: str = Form("0"),
    backtest: str = Form("0"),
):
    try:
        result, record_id = _run_and_save(
            codes, months, reasoning == "1", use_llm == "1", backtest == "1"
        )
        if record_id:
            result["_record_id"] = record_id
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )
