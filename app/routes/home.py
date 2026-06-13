"""GET /api/home/* — 首页仪表盘 API routes (funds overview dashboard)

Provides 6 endpoints for the home page overview:
  1. summary         — portfolio-wide aggregates & type breakdown
  2. nav_curves      — historical NAV curves with accumulated NAV
  3. type_distribution — fund type pie chart data
  4. risk_metrics    — MDD, volatility, risk rating, peer rank per fund
  5. list            — flat listing of all favorites with latest metrics
  6. refresh         — SSE stream for batch quote refresh
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.persistence import list_favorites
from app.services import quotes as quotes_svc
from app.services.quotes import get_favorite_with_metrics
from app.services.risk_metrics import (
    compute_max_drawdown,
    compute_risk_rating,
    compute_volatility,
)
from src.tools.api import fetch_fund_info, fetch_fund_metrics, fetch_nav_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home")


# ── helpers ──────────────────────────────────────────────────────────────


def _parse_codes(codes_str: str | None) -> list[str]:
    """Parse comma-separated fund codes. None or empty → all favorites."""
    if codes_str and codes_str.strip():
        return [c.strip() for c in codes_str.split(",") if c.strip()]
    return [f["code"] for f in list_favorites()]


def _navs_to_returns(nav_series: list[float]) -> list[float]:
    """Convert chronological NAV series to daily decimal returns."""
    if len(nav_series) < 2:
        return []
    return [(nav_series[i] - nav_series[i - 1]) / nav_series[i - 1] for i in range(1, len(nav_series))]


# ── routes ───────────────────────────────────────────────────────────────


@router.get("/summary")
async def home_summary() -> dict:
    """Portfolio-wide aggregates — total count, value, cost, gain %, and type breakdown."""
    favs = list_favorites()
    total_count = len(favs)
    total_cost = 0.0
    total_value = 0.0
    type_count: dict[str, int] = {}
    type_value: dict[str, float] = {}

    for fav in favs:
        code = fav["code"]
        cost = fav.get("buy_amount", 0) or 0
        total_cost += cost

        # Current market value
        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, code)
            val = m.current_value if m and m.current_value is not None else 0.0
        except Exception:
            logger.exception("Failed to get metrics for %s (summary)", code)
            val = 0.0
        total_value += val

        # Fund type
        try:
            info = await asyncio.to_thread(fetch_fund_info, code)
            ftype = info.type if info and info.type else "未知"
        except Exception:
            logger.exception("Failed to get fund info for %s (summary)", code)
            ftype = "未知"

        type_count[ftype] = type_count.get(ftype, 0) + 1
        type_value[ftype] = type_value.get(ftype, 0) + val

    total_gain_pct = round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0.0

    type_breakdown = [
        {
            "type": t,
            "count": type_count[t],
            "value_pct": round(type_value[t] / total_value * 100, 2) if total_value > 0 else 0.0,
        }
        for t in sorted(type_count, key=lambda x: type_value.get(x, 0), reverse=True)
    ]

    return {
        "total_count": total_count,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain_pct": total_gain_pct,
        "type_breakdown": type_breakdown,
    }


@router.get("/nav_curves")
async def home_nav_curves(
    codes: str | None = Query(None, description="逗号分隔的基金代码, 空=全部"),
    window: int = Query(12, ge=1, le=120, description="历史月数"),
) -> dict:
    """Historical NAV curves for selected funds.

    Returns dates, unit NAVs, and accumulated NAVs for each fund code.
    """
    fund_codes = _parse_codes(codes)
    curves: list[dict] = []

    for code in fund_codes:
        try:
            navs, info = await asyncio.gather(
                asyncio.to_thread(fetch_nav_history, code, window),
                asyncio.to_thread(fetch_fund_info, code),
            )
            curves.append({
                "code": code,
                "name": info.name if info and info.name else code,
                "dates": [n.date for n in navs],
                "navs": [n.nav for n in navs],
                "accumulated_navs": [n.acc_nav for n in navs],
            })
        except Exception:
            logger.exception("Failed to fetch nav curve for %s", code)
            curves.append({
                "code": code,
                "name": code,
                "dates": [],
                "navs": [],
                "accumulated_navs": [],
            })

    return {"curves": curves}


@router.get("/type_distribution")
async def home_type_distribution() -> dict:
    """Fund type distribution — for pie chart display."""
    favs = list_favorites()
    type_count: dict[str, int] = {}
    type_value: dict[str, float] = {}
    total_value = 0.0

    for fav in favs:
        code = fav["code"]

        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, code)
            val = m.current_value if m and m.current_value is not None else 0.0
        except Exception:
            logger.exception("Failed to get metrics for %s (type_distribution)", code)
            val = 0.0
        total_value += val

        try:
            info = await asyncio.to_thread(fetch_fund_info, code)
            ftype = info.type if info and info.type else "未知"
        except Exception:
            logger.exception("Failed to get fund info for %s (type_distribution)", code)
            ftype = "未知"

        type_count[ftype] = type_count.get(ftype, 0) + 1
        type_value[ftype] = type_value.get(ftype, 0) + val

    distribution = [
        {
            "type": t,
            "count": type_count[t],
            "value_pct": round(type_value[t] / total_value * 100, 2) if total_value > 0 else 0.0,
        }
        for t in sorted(type_count, key=lambda x: type_value.get(x, 0), reverse=True)
    ]

    return {"distribution": distribution}


@router.get("/risk_metrics")
async def home_risk_metrics(
    codes: str | None = Query(None, description="逗号分隔的基金代码, 空=全部"),
    window: int = Query(12, ge=1, le=120, description="计算窗口(月)"),
) -> dict:
    """Risk metrics per fund — MDD, volatility, star rating, peer rank."""
    fund_codes = _parse_codes(codes)
    metrics_list: list[dict] = []

    for code in fund_codes:
        try:
            navs, info, fund_metrics = await asyncio.gather(
                asyncio.to_thread(fetch_nav_history, code, window),
                asyncio.to_thread(fetch_fund_info, code),
                asyncio.to_thread(fetch_fund_metrics, code, window),
            )

            nav_series = [n.nav for n in navs if n.nav is not None]

            if len(nav_series) >= 2:
                mdd_result = compute_max_drawdown(nav_series)
                mdd_pct = mdd_result["mdd_pct"]  # negative percentage
                returns = _navs_to_returns(nav_series)
                vol = compute_volatility(returns)
                rating = compute_risk_rating(mdd_pct, vol)
            else:
                mdd_pct = 0.0
                vol = 0.0
                rating = "—"

            metrics_list.append({
                "code": code,
                "name": info.name if info and info.name else code,
                "mdd": round(mdd_pct, 2),
                "volatility": round(vol, 2),
                "rating": rating,
                "peer_rank": fund_metrics.ranking_1y if fund_metrics else None,
            })
        except Exception:
            logger.exception("Failed to compute risk metrics for %s", code)
            metrics_list.append({
                "code": code,
                "name": code,
                "mdd": None,
                "volatility": None,
                "rating": "—",
                "peer_rank": None,
            })

    return {"metrics": metrics_list}


@router.get("/list")
async def home_list() -> list:
    """Flat listing of all favorites with latest NAV, name, type, gain %, hold days."""
    favs = list_favorites()
    results: list[dict] = []

    for fav in favs:
        code = fav["code"]
        try:
            m, info = await asyncio.gather(
                asyncio.to_thread(get_favorite_with_metrics, code),
                asyncio.to_thread(fetch_fund_info, code),
            )

            nav = m.current_nav if m else None
            gain_pct = m.return_pct if m else None

            # Hold days from buy_date
            buy_date_str = fav.get("buy_date")
            hold_days: int | None = None
            if buy_date_str:
                try:
                    buy_dt = datetime.strptime(buy_date_str, "%Y-%m-%d")
                    hold_days = (datetime.now() - buy_dt).days
                except (ValueError, TypeError):
                    pass

            results.append({
                "code": code,
                "name": info.name if info and info.name else fav.get("name", ""),
                "type": info.type if info else (fav.get("type") or ""),
                "nav": nav,
                "accumulated_nav": None,
                "gain_pct": gain_pct,
                "hold_days": hold_days,
            })
        except Exception:
            logger.exception("Failed to get list data for %s", code)
            results.append({
                "code": code,
                "name": fav.get("name", ""),
                "type": fav.get("type", ""),
                "nav": None,
                "accumulated_nav": None,
                "gain_pct": None,
                "hold_days": None,
            })

    return results


@router.get("/refresh")
async def home_refresh(request: Request) -> Response:
    """SSE stream — batch refresh all favorites' quotes.

    Yields text/event-stream with start/progress/keep-alive/done events,
    matching the same format as /api/favorites/refresh.
    """
    if quotes_svc._refresh_running:
        raise HTTPException(status_code=409, detail="refresh already running")

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in quotes_svc.batch_refresh_quotes():
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            logger.info("SSE client disconnected from /api/home/refresh")
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
