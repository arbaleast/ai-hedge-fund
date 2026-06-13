"""GET /api/health/* — 5 API routes for portfolio health diagnosis page.

Provides endpoints for:
  1. summary            — portfolio health score (4 dimensions weighted)
  2. type_distribution  — fund type pie chart distribution
  3. holding_duration   — per-fund & average holding duration in months
  4. concentration      — top holdings weight concentration
  5. peer_compare       — per-fund return vs portfolio average
"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter

from app.persistence import list_favorites
from app.services.quotes import get_favorite_with_metrics
from app.services.risk_metrics import compute_health_score
from src.tools.api import fetch_fund_info, fetch_nav_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health")


# ── helpers ──────────────────────────────────────────────────────────────


def _months_since(date_str: str | None) -> float:
    """Calculate months from a date string to today."""
    if not date_str:
        return 0.0
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        now = datetime.now()
        return max(0.0, (now.year - dt.year) * 12 + (now.month - dt.month) + (now.day - dt.day) / 30.0)
    except (ValueError, TypeError):
        return 0.0


# ── routes ───────────────────────────────────────────────────────────────


@router.get("/summary")
async def health_summary() -> dict:
    """Portfolio health score — aggregated from 4 weighted dimensions.

    Uses compute_health_score() from risk_metrics service:
      concentration (30%) — penalty for >10% single-fund weight
      type_diversity (30%) — variety of asset types
      outperform (20%)     — NAV total return of reference fund
      holding_duration (20%) — average hold period in months
    """
    favs = list_favorites()
    if not favs:
        return {
            "health_score": 0.0,
            "concentration": 0.0,
            "type_diversity": 0.0,
            "outperform": 0.0,
            "holding_duration": 0.0,
        }

    # First pass: compute total current value across all favorites
    total_value = 0.0
    code_values: dict[str, float] = {}
    for fav in favs:
        code = fav["code"]
        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, code)
            val = m.current_value if m and m.current_value is not None else 0.0
        except Exception:
            logger.exception("Failed to get metrics for %s (health summary)", code)
            val = 0.0
        code_values[code] = val
        total_value += val

    # Second pass: build holdings with weight/type/duration; fetch nav series
    holdings: list[dict] = []
    ref_nav_series: list[float] = []
    for fav in favs:
        code = fav["code"]
        weight = code_values.get(code, 0.0) / total_value if total_value > 0 else 0.0

        try:
            info = await asyncio.to_thread(fetch_fund_info, code)
            ftype = info.type if info and info.type else "未知"
        except Exception:
            logger.exception("Failed to fetch fund info for %s (health summary)", code)
            ftype = "未知"

        duration = _months_since(fav.get("buy_date"))

        holdings.append({
            "weight": weight,
            "type": ftype,
            "duration": duration,
        })

        # Use first favorite's NAV as reference series for outperform scoring
        if not ref_nav_series:
            try:
                navs = await asyncio.to_thread(fetch_nav_history, code, 12)
                ref_nav_series = [n.nav for n in navs if n.nav is not None]
            except Exception:
                logger.exception("Failed to fetch nav history for %s (health summary)", code)

    result = compute_health_score(holdings, ref_nav_series)

    return {
        "health_score": round(result["total"], 2),
        "concentration": round(result["concentration"], 2),
        "type_diversity": round(result["type_diversity"], 2),
        "outperform": round(result["outperform"], 2),
        "holding_duration": round(result["holding_duration"], 2),
    }


@router.get("/type_distribution")
async def health_type_distribution() -> dict:
    """Fund type distribution — for pie chart display."""
    favs = list_favorites()
    total_value = 0.0
    type_count: dict[str, int] = {}
    type_value: dict[str, float] = {}

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
            logger.exception("Failed to fetch fund info for %s (type_distribution)", code)
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


@router.get("/holding_duration")
async def health_holding_duration() -> dict:
    """Holding duration per fund and portfolio average (in months)."""
    favs = list_favorites()
    holdings_list: list[dict] = []
    total_months = 0.0

    for fav in favs:
        code = fav["code"]
        duration = _months_since(fav.get("buy_date"))
        total_months += duration

        try:
            info = await asyncio.to_thread(fetch_fund_info, code)
            name = info.name if info and info.name else fav.get("name", "")
        except Exception:
            logger.exception("Failed to fetch fund info for %s (holding_duration)", code)
            name = fav.get("name", "")

        holdings_list.append({
            "code": code,
            "name": name,
            "duration_months": round(duration, 1),
        })

    holdings_list.sort(key=lambda x: x["duration_months"], reverse=True)
    avg_duration = round(total_months / len(favs), 1) if favs else 0.0

    return {
        "avg_duration_months": avg_duration,
        "holdings": holdings_list,
    }


@router.get("/concentration")
async def health_concentration() -> dict:
    """Portfolio concentration — individual & aggregate weight percentages."""
    favs = list_favorites()
    total_value = 0.0
    fund_values: list[dict] = []

    for fav in favs:
        code = fav["code"]
        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, code)
            val = m.current_value if m and m.current_value is not None else 0.0
            name = m.name if m and m.name else fav.get("name", "")
        except Exception:
            logger.exception("Failed to get metrics for %s (concentration)", code)
            val = 0.0
            name = fav.get("name", "")
        total_value += val
        fund_values.append({"code": code, "name": name, "value": val})

    top_holdings = []
    max_weight = 0.0
    for fv in fund_values:
        weight_pct = round(fv["value"] / total_value * 100, 2) if total_value > 0 else 0.0
        top_holdings.append({
            "code": fv["code"],
            "name": fv["name"],
            "weight_pct": weight_pct,
        })
        if weight_pct > max_weight:
            max_weight = weight_pct

    top_holdings.sort(key=lambda x: x["weight_pct"], reverse=True)

    return {
        "top_holdings": top_holdings,
        "max_weight": max_weight,
    }


@router.get("/peer_compare")
async def health_peer_compare() -> dict:
    """Per-fund return comparison vs portfolio average return."""
    favs = list_favorites()
    fund_returns: list[dict] = []
    total_return = 0.0
    count = 0

    for fav in favs:
        code = fav["code"]
        try:
            m = await asyncio.to_thread(get_favorite_with_metrics, code)
            ret = m.return_pct if m and m.return_pct is not None else None
            name = m.name if m and m.name else fav.get("name", "")
        except Exception:
            logger.exception("Failed to get metrics for %s (peer_compare)", code)
            ret = None
            name = fav.get("name", "")

        fund_returns.append({
            "code": code,
            "name": name,
            "return_pct": ret,
        })
        if ret is not None:
            total_return += ret
            count += 1

    avg_return = round(total_return / count, 4) if count > 0 else 0.0

    outperform = []
    for fr in fund_returns:
        vs_avg = round(fr["return_pct"] - avg_return, 4) if fr["return_pct"] is not None else None
        outperform.append({
            "code": fr["code"],
            "name": fr["name"],
            "return_pct": fr["return_pct"],
            "vs_avg": vs_avg,
        })

    return {"outperform": outperform}
