"""GET /api/detail/* — 8 API routes for single fund detail page.

Provides endpoints for:
  1. info         — basic info (name, type, manager, scale, inception_date)
  2. position     — top holdings & industry distribution
  3. quote        — latest NAV quote with daily return
  4. returns      — return time series & window summaries
  5. risk         — risk metrics (MDD, volatility, sharpe, rating, peer rank)
  6. nav_curve    — historical NAV curve (dates, unit NAVs, accumulated NAVs)
  7. drawdown     — drawdown series with peak/trough/recovery dates
  8. peer_compare — compare metrics with up to 5 peer funds from favorites
"""

import asyncio
import logging

from fastapi import APIRouter, Query

from app.persistence import list_favorites
from app.services.risk_metrics import (
    compute_max_drawdown,
    compute_risk_rating,
    compute_volatility,
)
from src.tools.api import (
    fetch_fund_info,
    fetch_fund_metrics,
    fetch_latest_nav,
    fetch_nav_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/detail")


# ── helpers ──────────────────────────────────────────────────────────────


def _navs_to_returns(nav_series: list[float]) -> list[float]:
    """Convert chronological NAV series to daily decimal returns."""
    if len(nav_series) < 2:
        return []
    return [(nav_series[i] - nav_series[i - 1]) / nav_series[i - 1] for i in range(1, len(nav_series))]


def _pick_window_return(metrics, window: int):
    """Pick the best-matching precomputed return from FundMetrics."""
    if metrics is None:
        return None
    if window <= 1:
        return metrics.return_1m
    if window <= 3:
        return metrics.return_3m
    if window <= 6:
        return metrics.return_6m
    if window <= 12:
        return metrics.return_1y
    if window <= 36:
        return metrics.return_3y
    return metrics.return_ytd


# ── routes ───────────────────────────────────────────────────────────────


@router.get("/{code}/info")
async def detail_info(code: str) -> dict:
    """Fund basic info — name, type, manager, scale, inception_date."""
    try:
        info = await asyncio.to_thread(fetch_fund_info, code)
        if not info:
            return {"name": "", "type": "", "manager": "", "scale": None, "inception_date": None}
        return {
            "name": info.name or "",
            "type": info.type or "",
            "manager": info.manager or "",
            "scale": info.fund_size if info.fund_size else None,
            "inception_date": info.establish_date or None,
        }
    except Exception:
        logger.exception("Failed to fetch info for %s", code)
        return {"name": "", "type": "", "manager": "", "scale": None, "inception_date": None}


@router.get("/{code}/position")
async def detail_position(code: str) -> dict:
    """Top holdings (name, weight, change) and industry distribution."""
    try:
        metrics = await asyncio.to_thread(fetch_fund_metrics, code, 12)
        if not metrics:
            return {"top_holdings": [], "industry_distribution": []}

        top_holdings = [
            {
                "name": h.name or "",
                "weight": h.ratio,
                "change": None,
            }
            for h in metrics.top_holdings
        ]

        industry_distribution = [
            {"industry": k, "value": v}
            for k, v in (metrics.sector_allocation or {}).items()
        ]

        return {
            "top_holdings": top_holdings,
            "industry_distribution": industry_distribution,
        }
    except Exception:
        logger.exception("Failed to fetch position for %s", code)
        return {"top_holdings": [], "industry_distribution": []}


@router.get("/{code}/quote")
async def detail_quote(code: str) -> dict:
    """Latest NAV quote — nav, accumulated_nav, nav_date, daily_return, premium_discount."""
    try:
        nav_data, nav_history = await asyncio.gather(
            asyncio.to_thread(fetch_latest_nav, code),
            asyncio.to_thread(fetch_nav_history, code, 1),
        )

        nav = nav_data["nav"] if nav_data else (nav_history[-1].nav if nav_history else None)
        nav_date = nav_data["date"] if nav_data else (nav_history[-1].date if nav_history else None)

        # accumulated_nav: prefer acc_nav field, fallback to unit nav
        accumulated_nav = nav
        if nav_history and nav_history[-1].acc_nav is not None:
            accumulated_nav = nav_history[-1].acc_nav

        # daily_return from last two NAV points
        daily_return = None
        if len(nav_history) >= 2:
            latest = nav_history[-1].nav
            prev = nav_history[-2].nav
            if prev:
                daily_return = round((latest - prev) / prev * 100, 4)

        return {
            "nav": nav,
            "accumulated_nav": accumulated_nav,
            "nav_date": nav_date,
            "daily_return": daily_return,
            "premium_discount": None,
        }
    except Exception:
        logger.exception("Failed to fetch quote for %s", code)
        return {
            "nav": None,
            "accumulated_nav": None,
            "nav_date": None,
            "daily_return": None,
            "premium_discount": None,
        }


@router.get("/{code}/returns")
async def detail_returns(
    code: str,
    window: int = Query(12, ge=1, le=120, description="历史月数"),
) -> dict:
    """Return time series and window summary — nav_return & accumulated_return per date."""
    try:
        navs, metrics = await asyncio.gather(
            asyncio.to_thread(fetch_nav_history, code, window),
            asyncio.to_thread(fetch_fund_metrics, code, window),
        )

        returns_series = []
        if len(navs) >= 2:
            base_nav = navs[0].nav
            for i in range(1, len(navs)):
                prev_nav = navs[i - 1].nav
                curr_nav = navs[i].nav
                if prev_nav and base_nav:
                    nav_return = round((curr_nav - prev_nav) / prev_nav * 100, 4)
                    acc_return = round((curr_nav - base_nav) / base_nav * 100, 4)
                else:
                    nav_return = None
                    acc_return = None
                returns_series.append({
                    "date": navs[i].date,
                    "nav_return": nav_return,
                    "accumulated_return": acc_return,
                })

        windows = {}
        if metrics:
            windows = {
                "1m": metrics.return_1m,
                "3m": metrics.return_3m,
                "6m": metrics.return_6m,
                "1y": metrics.return_1y,
                "3y": metrics.return_3y,
                "ytd": metrics.return_ytd,
            }

        return {"returns": returns_series, "windows": windows}
    except Exception:
        logger.exception("Failed to fetch returns for %s", code)
        return {"returns": [], "windows": {}}


@router.get("/{code}/risk")
async def detail_risk(
    code: str,
    window: int = Query(12, ge=1, le=120, description="计算窗口(月)"),
) -> dict:
    """Risk metrics — MDD, drawdown days, volatility, sharpe, star rating, peer rank."""
    try:
        navs, metrics = await asyncio.gather(
            asyncio.to_thread(fetch_nav_history, code, window),
            asyncio.to_thread(fetch_fund_metrics, code, window),
        )

        nav_series = [n.nav for n in navs if n.nav is not None]

        if len(nav_series) >= 2:
            mdd_result = compute_max_drawdown(nav_series)
            mdd_pct = mdd_result["mdd_pct"]
            mdd_days = None
            if mdd_result["trough_date"] is not None and mdd_result["peak_date"] is not None:
                mdd_days = mdd_result["trough_date"] - mdd_result["peak_date"]
            returns = _navs_to_returns(nav_series)
            vol = compute_volatility(returns)
            rating = compute_risk_rating(mdd_pct, vol)
        else:
            mdd_pct = 0.0
            mdd_days = None
            vol = 0.0
            rating = "—"

        return {
            "mdd": round(mdd_pct, 2),
            "mdd_days": mdd_days,
            "volatility": round(vol, 2),
            "sharpe": round(metrics.sharpe_ratio, 2) if metrics and metrics.sharpe_ratio is not None else None,
            "rating": rating,
            "peer_rank": metrics.ranking_1y if metrics else None,
        }
    except Exception:
        logger.exception("Failed to compute risk metrics for %s", code)
        return {
            "mdd": None,
            "mdd_days": None,
            "volatility": None,
            "sharpe": None,
            "rating": "—",
            "peer_rank": None,
        }


@router.get("/{code}/nav_curve")
async def detail_nav_curve(
    code: str,
    window: int = Query(12, ge=1, le=120, description="历史月数"),
) -> dict:
    """Historical NAV curve — dates, unit NAVs, accumulated NAVs."""
    try:
        navs = await asyncio.to_thread(fetch_nav_history, code, window)
        return {
            "dates": [n.date for n in navs],
            "navs": [n.nav for n in navs],
            "accumulated_navs": [n.acc_nav if n.acc_nav is not None else n.nav for n in navs],
        }
    except Exception:
        logger.exception("Failed to fetch nav curve for %s", code)
        return {"dates": [], "navs": [], "accumulated_navs": []}


@router.get("/{code}/drawdown")
async def detail_drawdown(
    code: str,
    window: int = Query(12, ge=1, le=120, description="历史月数"),
) -> dict:
    """Drawdown series — drawdown_pct per date, plus peak/trough/recovery dates."""
    try:
        navs = await asyncio.to_thread(fetch_nav_history, code, window)
        nav_series = [n.nav for n in navs if n.nav is not None]
        dates = [n.date for n in navs if n.nav is not None]

        if len(nav_series) < 2:
            return {"drawdown_series": [], "peak": None, "trough": None, "recovery": None}

        mdd_result = compute_max_drawdown(nav_series)

        # Build running drawdown series
        running_peak = nav_series[0]
        drawdown_series = []
        for i, val in enumerate(nav_series):
            if val > running_peak:
                running_peak = val
            dd = (val - running_peak) / running_peak * 100
            drawdown_series.append({
                "date": dates[i],
                "drawdown_pct": round(dd, 2),
            })

        peak_date = dates[mdd_result["peak_date"]] if mdd_result["peak_date"] is not None else None
        trough_date = dates[mdd_result["trough_date"]] if mdd_result["trough_date"] is not None else None
        recovery_date = dates[mdd_result["recovery_date"]] if mdd_result["recovery_date"] is not None else None

        return {
            "drawdown_series": drawdown_series,
            "peak": peak_date,
            "trough": trough_date,
            "recovery": recovery_date,
        }
    except Exception:
        logger.exception("Failed to compute drawdown for %s", code)
        return {"drawdown_series": [], "peak": None, "trough": None, "recovery": None}


@router.get("/{code}/peer_compare")
async def detail_peer_compare(
    code: str,
    window: int = Query(12, ge=1, le=120, description="历史月数"),
) -> dict:
    """Compare metrics with up to 5 peer funds (favorites excluding current fund)."""
    try:
        favs = list_favorites()
        peer_codes = [f["code"] for f in favs if f["code"] != code][:5]
        peer_metrics: list[dict] = []

        for peer_code in peer_codes:
            try:
                navs, info, fund_metrics = await asyncio.gather(
                    asyncio.to_thread(fetch_nav_history, peer_code, window),
                    asyncio.to_thread(fetch_fund_info, peer_code),
                    asyncio.to_thread(fetch_fund_metrics, peer_code, window),
                )

                nav_series = [n.nav for n in navs if n.nav is not None]

                if len(nav_series) >= 2:
                    mdd_result = compute_max_drawdown(nav_series)
                    mdd_pct = mdd_result["mdd_pct"]
                    returns = _navs_to_returns(nav_series)
                    vol = compute_volatility(returns)
                    rating = compute_risk_rating(mdd_pct, vol)
                else:
                    mdd_pct = 0.0
                    vol = 0.0
                    rating = "—"

                peer_return = _pick_window_return(fund_metrics, window)
                peer_metrics.append({
                    "code": peer_code,
                    "name": info.name if info and info.name else peer_code,
                    "return_pct": peer_return,
                    "mdd": round(mdd_pct, 2),
                    "volatility": round(vol, 2),
                    "rating": rating,
                })
            except Exception:
                logger.exception("Failed to compute peer metrics for %s", peer_code)
                continue

        return {"peer_metrics": peer_metrics}
    except Exception:
        logger.exception("Failed to compute peer compare for %s", code)
        return {"peer_metrics": []}
