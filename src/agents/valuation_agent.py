"""估值分析 Agent — 分析QDII/指数基金当前净值的历史分位"""

import numpy as np
from datetime import datetime
from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


def fund_valuation_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """估值分析: 基于NAV历史分位判断当前估值高低
    - 对于QDII/指数基金特别有用
    - 使用z-score和百分位分析
    """

    if not navs or len(navs) < 30:
        return FundSignal(
            signal="neutral",
            confidence=0,
            score=50,
            reasoning={"error": "数据不足,需要至少30天历史"},
        )

    nav_values = np.array([n.nav for n in navs])
    current_nav = nav_values[-1]

    # 计算统计指标
    mean_nav = float(np.mean(nav_values))
    std_nav = float(np.std(nav_values))
    min_nav = float(np.min(nav_values))
    max_nav = float(np.max(nav_values))

    # Z-score: 当前价格偏离均值的标准差
    if std_nav > 0:
        z_score = (current_nav - mean_nav) / std_nav
    else:
        z_score = 0.0

    # 百分位: 当前价格在历史中的位置
    percentile = float(np.sum(nav_values < current_nav) / len(nav_values)) * 100

    # === 估值评分 ===
    val_score = 50  # 基础分
    reasons = []

    # 分位分析
    if percentile < 20:
        val_score += 25
        reasons.append(f"估值极低({percentile:.1f}%分位),历史底部区域")
    elif percentile < 35:
        val_score += 15
        reasons.append(f"估值偏低({percentile:.1f}%分位)")
    elif percentile > 80:
        val_score -= 25
        reasons.append(f"估值极高({percentile:.1f}%分位),历史高位")
    elif percentile > 65:
        val_score -= 15
        reasons.append(f"估值偏高({percentile:.1f}%分位)")
    else:
        reasons.append(f"估值合理({percentile:.1f}%分位)")

    # Z-score分析
    if z_score < -1.5:
        val_score += 10
        reasons.append(f"Z分数低({z_score:.2f}),明显低于历史均价")
    elif z_score < -1.0:
        val_score += 5
        reasons.append(f"Z分数偏低({z_score:.2f})")
    elif z_score > 1.5:
        val_score -= 10
        reasons.append(f"Z分数高({z_score:.2f}),明显高于历史均价")
    elif z_score > 1.0:
        val_score -= 5
        reasons.append(f"Z分数偏高({z_score:.2f})")

    # 距历史高/低点的距离
    if max_nav > min_nav:
        dist_to_high = (max_nav - current_nav) / (max_nav - min_nav) * 100
        dist_to_low = (current_nav - min_nav) / (max_nav - min_nav) * 100
        reasons.append(f"距历史高点{dist_to_high:.1f}%,距历史低点{dist_to_low:.1f}%")

    # 基金类型调整
    fund_type = info.type.lower() if info and info.type else ""
    is_qdii = "qdii" in fund_type or "境外" in fund_type
    is_index = "指数" in fund_type

    if is_qdii:
        reasons.append("QDII基金: 估值受汇率和海外市场影响")
        val_score = max(0, val_score - 5)  # QDII不确定性高,略微降低评分
    if is_index:
        reasons.append("指数基金: 适合定投,估值仅作参考")
        # 指数基金估值权重降低,但仍提供参考

    # 限制在0-100范围
    val_score = max(0, min(100, val_score))

    # === 信号判定 ===
    if val_score >= 65:
        signal = "bullish"
        confidence = min(95, 50 + (val_score - 65) * 1.5)
    elif val_score <= 35:
        signal = "bearish"
        confidence = min(95, 50 + (35 - val_score) * 1.5)
    else:
        signal = "neutral"
        confidence = 50

    return FundSignal(
        signal=signal,
        confidence=round(confidence, 1),
        score=round(val_score, 1),
        reasoning={
            "估值得分": round(val_score, 1),
            "历史分位": f"{percentile:.1f}%",
            "Z分数": round(z_score, 2),
            "当前净值": round(current_nav, 3),
            "历史均值": round(mean_nav, 3),
            "历史高点": round(max_nav, 3),
            "历史低点": round(min_nav, 3),
            "分析要点": reasons,
            "基金类型": info.type or "未知",
        },
    )
