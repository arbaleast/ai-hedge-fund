"""实时行情 + 持仓指标计算 — async 服务层"""

import asyncio
import logging
import time
from dataclasses import dataclass
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
