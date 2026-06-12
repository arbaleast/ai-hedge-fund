"""风险分析 Agent — 分析最大回撤、波动率、夏普比率等风险指标"""

import numpy as np
from datetime import datetime, timedelta
from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


# 风险评分基准 (仅供参考,实际因基金类型而异)
RISK_BENCHMARKS = {
    "volatility_1y": {"low": 10, "medium": 20, "high": 30},  # 波动率
    "max_drawdown_1y": {"low": 10, "medium": 20, "high": 30},  # 最大回撤
    "sharpe_ratio": {"good": 1.0, "fair": 0.5, "poor": 0.0},  # 夏普比率
}


def risk_analysis_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """分析基金风险指标: 最大回撤、波动率、夏普比率"""

    reasons = []
    risk_score = 50  # 基础分 (越低越安全)

    # === 波动率分析 ===
    volatility = metrics.volatility_1y
    if volatility is not None:
        if volatility < 10:
            risk_score -= 15
            reasons.append(f"波动率极低({volatility:.1f}%),风险可控")
        elif volatility < 20:
            risk_score -= 5
            reasons.append(f"波动率较低({volatility:.1f}%)")
        elif volatility > 35:
            risk_score += 20
            reasons.append(f"波动率偏高({volatility:.1f}%),注意风险")
        else:
            risk_score += 10
            reasons.append(f"波动率中等({volatility:.1f}%)")

    # === 最大回撤分析 ===
    max_dd = metrics.max_drawdown_1y
    if max_dd is not None:
        if max_dd < 10:
            risk_score -= 15
            reasons.append(f"最大回撤极小({max_dd:.1f}%),风险控制优秀")
        elif max_dd < 20:
            risk_score -= 5
            reasons.append(f"最大回撤可控({max_dd:.1f}%)")
        elif max_dd > 35:
            risk_score += 20
            reasons.append(f"最大回撤较大({max_dd:.1f}%),需注意")
        else:
            risk_score += 10
            reasons.append(f"最大回撤中等({max_dd:.1f}%)")

    # === 夏普比率分析 (风险调整收益) ===
    sharpe = metrics.sharpe_ratio
    if sharpe is not None:
        if sharpe > 1.5:
            risk_score -= 15
            reasons.append(f"夏普比率优秀({sharpe:.2f}),风险调整收益高")
        elif sharpe > 1.0:
            risk_score -= 5
            reasons.append(f"夏普比率良好({sharpe:.2f})")
        elif sharpe < 0:
            risk_score += 15
            reasons.append(f"夏普比率为负({sharpe:.2f}),收益不及无风险利率")
        else:
            risk_score += 5
            reasons.append(f"夏普比率一般({sharpe:.2f})")

    # === 收益风险比 (如果无法计算夏普比率,用收益/回撤比) ===
    if sharpe is None and metrics.return_1y is not None and max_dd and max_dd > 0:
        rr_ratio = metrics.return_1y / max_dd
        if rr_ratio > 1.5:
            risk_score -= 10
            reasons.append(f"收益回撤比优秀({rr_ratio:.2f})")
        elif rr_ratio > 1.0:
            risk_score -= 5
            reasons.append(f"收益回撤比良好({rr_ratio:.2f})")
        elif rr_ratio < 0.5:
            risk_score += 10
            reasons.append(f"收益回撤比较低({rr_ratio:.2f})")

    # === 基金类型调整 ===
    fund_type = info.type.lower() if info and info.type else ""
    if "债券" in fund_type or "纯债" in fund_type:
        risk_score = max(0, risk_score - 10)  # 债券基金降低风险预期
        reasons.append("债券型基金,风险等级偏低")
    elif "股票" in fund_type or "指数" in fund_type:
        risk_score = min(100, risk_score + 5)  # 股票/指数基金提高风险预期
        reasons.append("股票/指数型基金,风险等级偏高")

    # 限制在0-100范围
    risk_score = max(0, min(100, risk_score))

    # === 信号判定 ===
    # 注意: 风险分数越高表示风险越大,所以bullish/be bearish是反的
    # 但FundSignal的语义是: bullish=建议买入, bearish=建议卖出
    # 对于风险分析: 我们希望低风险得分高,高风险得分低
    # 所以最终得分 = 100 - risk_score (分数越高越安全)

    safety_score = 100 - risk_score

    if safety_score >= 65:
        signal = "bullish"
        confidence = min(95, 50 + (safety_score - 65) * 1.5)
    elif safety_score <= 35:
        signal = "bearish"
        confidence = min(95, 50 + (35 - safety_score) * 1.5)
    else:
        signal = "neutral"
        confidence = 50

    return FundSignal(
        signal=signal,
        confidence=round(confidence, 1),
        score=round(safety_score, 1),
        reasoning={
            "风险得分": round(risk_score, 1),
            "安全评分": round(safety_score, 1),
            "分析要点": reasons,
            "波动率": volatility,
            "最大回撤": max_dd,
            "夏普比率": sharpe,
        },
    )
