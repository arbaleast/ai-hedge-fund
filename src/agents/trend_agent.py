"""趋势分析 Agent — 分析基金净值趋势、均线位置、动量"""

import numpy as np
from datetime import datetime, timedelta
from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


def trend_analysis_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """分析基金NAV趋势: 移动均线、动量、相对位置"""

    if not navs or len(navs) < 20:
        return FundSignal(
            signal="neutral",
            confidence=0,
            score=0,
            reasoning={"error": "数据不足"},
        )

    # 转换为numpy数组便于计算
    nav_values = np.array([n.nav for n in navs])
    dates = [datetime.strptime(n.date, "%Y-%m-%d") for n in navs]

    # 计算移动平均
    ma20 = _sma(nav_values, 20)
    ma60 = _sma(nav_values, 60)
    ma120 = _sma(nav_values, 120)

    current_nav = nav_values[-1]

    # === 趋势评分 ===
    trend_score = 50  # 基础分
    reasons = []

    # 1. 价格与均线关系
    if ma20 is not None:
        if current_nav > ma20:
            trend_score += 15
            reasons.append(f"现价({current_nav:.3f})>MA20({ma20:.3f})")
        else:
            trend_score -= 15
            reasons.append(f"现价({current_nav:.3f})<MA20({ma20:.3f})")

    if ma60 is not None:
        if current_nav > ma60:
            trend_score += 15
            reasons.append(f"现价>MA60({ma60:.3f})")
        else:
            trend_score -= 15
            reasons.append(f"现价<MA60({ma60:.3f})")

    if ma120 is not None:
        if current_nav > ma120:
            trend_score += 10
            reasons.append(f"现价>MA120({ma120:.3f})")
        else:
            trend_score -= 10
            reasons.append(f"现价<MA120({ma120:.3f})")

    # 2. 均线多头排列 (短期>中期>长期)
    if ma20 and ma60 and ma120:
        if ma20 > ma60 > ma120:
            trend_score += 10
            reasons.append("均线多头排列")
        elif ma20 < ma60 < ma120:
            trend_score -= 10
            reasons.append("均线空头排列")

    # 3. 动量分析 (近1月、3月涨跌)
    if metrics.return_1m is not None:
        if metrics.return_1m > 5:
            trend_score += 10
            reasons.append(f"近1月涨幅{metrics.return_1m:.1f}%")
        elif metrics.return_1m < -5:
            trend_score -= 10
            reasons.append(f"近1月跌幅{metrics.return_1m:.1f}%")

    if metrics.return_3m is not None:
        if metrics.return_3m > 10:
            trend_score += 10
            reasons.append(f"近3月涨幅{metrics.return_3m:.1f}%")
        elif metrics.return_3m < -10:
            trend_score -= 10
            reasons.append(f"近3月跌幅{metrics.return_3m:.1f}%")

    # 4. 近期趋势强度 (20日斜率)
    if len(navs) >= 20:
        recent_20 = nav_values[-20:]
        slope = _linear_slope(recent_20)
        if slope > 0.001:
            trend_score += 5
            reasons.append("短期上升趋势")
        elif slope < -0.001:
            trend_score -= 5
            reasons.append("短期下降趋势")

    # 限制在0-100范围
    trend_score = max(0, min(100, trend_score))

    # === 信号判定 ===
    if trend_score >= 65:
        signal = "bullish"
        confidence = min(95, 50 + (trend_score - 65) * 1.5)
    elif trend_score <= 35:
        signal = "bearish"
        confidence = min(95, 50 + (35 - trend_score) * 1.5)
    else:
        signal = "neutral"
        confidence = 50

    return FundSignal(
        signal=signal,
        confidence=round(confidence, 1),
        score=round(trend_score, 1),
        reasoning={
            "趋势得分": round(trend_score, 1),
            "均线分析": reasons,
            "MA20": round(ma20, 3) if ma20 else None,
            "MA60": round(ma60, 3) if ma60 else None,
            "MA120": round(ma120, 3) if ma120 else None,
            "最新净值": round(current_nav, 3),
        },
    )


def _sma(arr: np.ndarray, period: int) -> float | None:
    """简单移动平均"""
    if len(arr) < period:
        return None
    return float(np.mean(arr[-period:]))


def _linear_slope(arr: np.ndarray) -> float:
    """线性回归斜率 (归一化)"""
    if len(arr) < 2:
        return 0.0
    x = np.arange(len(arr))
    x_mean = x.mean()
    y_mean = arr.mean()
    slope = np.sum((x - x_mean) * (arr - y_mean)) / np.sum((x - x_mean) ** 2)
    # 归一化: 除以平均值避免量纲影响
    if y_mean != 0:
        slope = slope / y_mean
    return float(slope)
