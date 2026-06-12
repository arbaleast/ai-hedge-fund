"""实时行情 + 持仓指标计算 — async 服务层"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.tools.api import fetch_latest_nav
from app.persistence import list_favorites

logger = logging.getLogger(__name__)


@dataclass
class QuoteResponse:
    """单基金实时行情响应"""
    code: str
    name: str
    nav: float
    date: str           # ISO date
    source: str = "eastmoney_gz"


@dataclass
class FavoriteWithMetrics:
    """持仓基金 + 实时指标"""
    code: str
    name: str
    buy_price: Optional[float]
    buy_amount: Optional[float]
    buy_date: Optional[str]
    current_nav: Optional[float]
    current_value: Optional[float]
    return_pct: Optional[float]      # None 表示 buy_price 或 current_nav 缺失
    max_drawdown: Optional[float]    # None 表示数据不足
    status: str = "ok"               # ok | error | incomplete


# ===== TTL cache (60s) =====
_quote_cache: dict[str, tuple[float, QuoteResponse]] = {}
QUOTE_TTL_SEC = 60


async def fetch_quote(code: str) -> Optional[QuoteResponse]:
    """单基金实时 NAV, 60s TTL cache. None 表示拉取失败."""
    now = time.time()
    if code in _quote_cache:
        cached_at, cached_quote = _quote_cache[code]
        if now - cached_at < QUOTE_TTL_SEC:
            return cached_quote

    raw = await asyncio.to_thread(fetch_latest_nav, code)
    if not raw:
        return None

    quote = QuoteResponse(
        code=code,
        name=raw.get("name", ""),
        nav=raw["nav"],
        date=raw["date"],
    )
    _quote_cache[code] = (now, quote)
    return quote


def compute_max_drawdown(navs: list[float]) -> Optional[float]:
    """
    Peak-to-trough 最大回撤 (从 buy_date 到 today).
    返回 0.0 ~ 1.0 (例如 0.235 = 23.5%). None 表示数据不足.
    """
    if not navs or len(navs) < 2:
        return None
    peak = navs[0]
    max_dd = 0.0
    for nav in navs:
        if nav > peak:
            peak = nav
        if peak > 0:
            dd = (peak - nav) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


# ===== 模块级锁 & 状态 flag =====
_refresh_lock: asyncio.Lock = asyncio.Lock()
_refresh_running: bool = False


def _date_to_ts(date_str: str) -> int:
    """YYYY-MM-DD -> epoch seconds. Returns 0 on failure."""
    try:
        return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())
    except (ValueError, TypeError):
        return 0


# fetch_nav_history 在 src.tools.api 中已存在; 退化为空列表保护
try:
    from src.tools.api import fetch_nav_history  # noqa: F811
except ImportError:
    logger.warning("fetch_nav_history not available; max_drawdown will be None")
    fetch_nav_history = lambda code, **kw: []  # type: ignore[assignment]


def get_favorite_with_metrics(code: str) -> Optional[FavoriteWithMetrics]:
    """
    同步函数:
    1. list_favorites() 找到 row
    2. asyncio.run(fetch_quote(code)) 拿 quote
    3. fetch_nav_history(code, months=3) 算 max_drawdown
    4. 计算 shares/current_value/return_pct
    """
    favs = list_favorites()
    row = None
    for fav in favs:
        if fav["code"] == code:
            row = fav
            break
    if not row:
        return None

    quote = asyncio.run(fetch_quote(code))

    buy_price: Optional[float] = row.get("buy_price")
    buy_amount: Optional[float] = row.get("buy_amount")
    buy_date: Optional[str] = row.get("buy_date")

    current_nav = quote.nav if quote else None
    current_value: Optional[float] = None
    return_pct: Optional[float] = None
    max_dd: Optional[float] = None

    if buy_price and buy_amount and current_nav:
        shares = buy_amount / buy_price
        current_value = shares * current_nav
        return_pct = (current_value - buy_amount) / buy_amount

    # max_drawdown from nav history (~90 days = 3 months)
    if buy_date and current_nav:
        try:
            navs_raw = fetch_nav_history(code, months=3)
            navs = [n.nav for n in navs_raw if n.nav is not None]
            max_dd = compute_max_drawdown(navs)
        except Exception:
            logger.warning("Failed to compute max_drawdown for %s", code, exc_info=True)

    if not quote:
        status = "no_quote"
    elif max_dd is None:
        status = "no_history"
    else:
        status = "ok"

    return FavoriteWithMetrics(
        code=code,
        name=row.get("name", ""),
        buy_price=buy_price,
        buy_amount=buy_amount,
        buy_date=buy_date,
        current_nav=current_nav,
        current_value=current_value,
        return_pct=return_pct,
        max_drawdown=max_dd,
        status=status,
    )


async def batch_refresh_quotes() -> AsyncGenerator[dict, None]:
    """
    SSE 事件流 — asyncio.Semaphore(3) 限速并发:
    - start:   {"event": "start", "total": N}
    - progress:{"event": "progress", "code": ..., "ok": bool, "fail": bool}
    - keep-al: {"event": "keep-alive", "ts": ...}  (20s 无 progress)
    - done:    {"event": "done", "ok": X, "fail": Y}
    """
    global _refresh_running
    async with _refresh_lock:
        if _refresh_running:
            return

        _refresh_running = True
        try:
            favs = list_favorites()
            total = len(favs)
            start_ts = time.time()

            yield {"event": "start", "total": total}

            if total == 0:
                yield {"event": "done", "ok": 0, "fail": 0}
                return

            sem = asyncio.Semaphore(3)
            ok_count = 0
            fail_count = 0
            last_activity = time.time()

            async def refresh_one(fav: dict) -> dict:
                nonlocal ok_count, fail_count
                async with sem:
                    code = fav["code"]
                    # 绕过 60s cache 强制刷新
                    _quote_cache.pop(code, None)
                    try:
                        quote = await fetch_quote(code)
                        if quote:
                            ok_count += 1
                            return {"event": "progress", "code": code, "ok": True, "fail": False}
                        else:
                            fail_count += 1
                            return {"event": "progress", "code": code, "ok": False, "fail": True}
                    except Exception:
                        fail_count += 1
                        logger.exception("Failed to refresh %s", code)
                        return {"event": "progress", "code": code, "ok": False, "fail": True}

            tasks = [asyncio.create_task(refresh_one(f)) for f in favs]
            for coro in asyncio.as_completed(tasks):
                now = time.time()
                if now - last_activity >= 20:
                    yield {"event": "keep-alive", "ts": int(now)}
                    last_activity = now
                yield await coro
                last_activity = time.time()

            yield {"event": "done", "ok": ok_count, "fail": fail_count}
        finally:
            _refresh_running = False
