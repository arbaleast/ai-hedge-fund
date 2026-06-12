"""同类对比 Agent — 基于收益率指标的同类基金对比分析"""

from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


def peer_comparison_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """同类对比: 基于收益率指标的Peer Comparison
    - 使用1月/3月/6月/1年收益率进行同类排名模拟
    - 假设各期限收益率均为正时更优
    """

    reasons = []
    peer_score = 50  # 基础分

    # 各期限收益率
    ret_1m = metrics.return_1m
    ret_3m = metrics.return_3m
    ret_6m = metrics.return_6m
    ret_1y = metrics.return_1y

    # === 短期收益分析 (1月) ===
    if ret_1m is not None:
        if ret_1m > 5:
            peer_score += 10
            reasons.append(f"近1月涨幅{ret_1m:.1f}%,表现强劲")
        elif ret_1m > 2:
            peer_score += 5
            reasons.append(f"近1月涨幅{ret_1m:.1f}%,表现良好")
        elif ret_1m < -5:
            peer_score -= 10
            reasons.append(f"近1月跌幅{ret_1m:.1f}%,表现较弱")
        elif ret_1m < -2:
            peer_score -= 5
            reasons.append(f"近1月下跌{ret_1m:.1f}%,短期走弱")
        else:
            reasons.append(f"近1月{ret_1m:.1f}%,表现平稳")
    else:
        reasons.append("近1月数据缺失")

    # === 中期收益分析 (3月) ===
    if ret_3m is not None:
        if ret_3m > 15:
            peer_score += 15
            reasons.append(f"近3月涨幅{ret_3m:.1f}%,中期表现优秀")
        elif ret_3m > 5:
            peer_score += 8
            reasons.append(f"近3月涨幅{ret_3m:.1f}%,中期表现良好")
        elif ret_3m < -10:
            peer_score -= 15
            reasons.append(f"近3月跌幅{ret_3m:.1f}%,中期表现较弱")
        elif ret_3m < -3:
            peer_score -= 8
            reasons.append(f"近3月下跌{ret_3m:.1f}%,中期走弱")
        else:
            reasons.append(f"近3月{ret_3m:.1f}%,中期平稳")
    else:
        reasons.append("近3月数据缺失")

    # === 长期收益分析 (6月) ===
    if ret_6m is not None:
        if ret_6m > 20:
            peer_score += 15
            reasons.append(f"近6月涨幅{ret_6m:.1f}%,长期表现优秀")
        elif ret_6m > 8:
            peer_score += 8
            reasons.append(f"近6月涨幅{ret_6m:.1f}%,长期表现良好")
        elif ret_6m < -15:
            peer_score -= 15
            reasons.append(f"近6月跌幅{ret_6m:.1f}%,长期表现较弱")
        elif ret_6m < -5:
            peer_score -= 8
            reasons.append(f"近6月下跌{ret_6m:.1f}%,长期走弱")
        else:
            reasons.append(f"近6月{ret_6m:.1f}%,长期平稳")
    else:
        reasons.append("近6月数据缺失")

    # === 1年收益分析 ===
    if ret_1y is not None:
        if ret_1y > 30:
            peer_score += 20
            reasons.append(f"近1年涨幅{ret_1y:.1f}%,年度收益优秀")
        elif ret_1y > 10:
            peer_score += 10
            reasons.append(f"近1年涨幅{ret_1y:.1f}%,年度收益良好")
        elif ret_1y < -15:
            peer_score -= 20
            reasons.append(f"近1年跌幅{ret_1y:.1f}%,年度收益较差")
        elif ret_1y < 0:
            peer_score -= 10
            reasons.append(f"近1年负收益{ret_1y:.1f}%,跑输市场")
        else:
            reasons.append(f"近1年{ret_1y:.1f}%,年度收益一般")
    else:
        reasons.append("近1年数据缺失")

    # === 综合持续性加分 ===
    positive_periods = sum(1 for r in [ret_1m, ret_3m, ret_6m, ret_1y] if r is not None and r > 0)
    if positive_periods >= 4:
        peer_score += 10
        reasons.append("各期限收益均为正,持续性强")
    elif positive_periods == 0 and all(r is not None for r in [ret_1m, ret_3m, ret_6m, ret_1y]):
        peer_score -= 10
        reasons.append("各期限收益均为负,持续性差")

    # === 近期vs长期趋势 ===
    if ret_1m is not None and ret_3m is not None and ret_3m != 0:
        momentum = ret_1m - (ret_3m / 3)  # 月均vs当前月
        if momentum > 2:
            peer_score += 5
            reasons.append("短期动能加速")
        elif momentum < -2:
            peer_score -= 5
            reasons.append("短期动能衰减")

    # 限制在0-100范围
    peer_score = max(0, min(100, peer_score))

    # === 信号判定 ===
    if peer_score >= 65:
        signal = "bullish"
        confidence = min(95, 50 + (peer_score - 65) * 1.5)
    elif peer_score <= 35:
        signal = "bearish"
        confidence = min(95, 50 + (35 - peer_score) * 1.5)
    else:
        signal = "neutral"
        confidence = 50

    return FundSignal(
        signal=signal,
        confidence=round(confidence, 1),
        score=round(peer_score, 1),
        reasoning={
            "对比得分": round(peer_score, 1),
            "分析要点": reasons,
            "近1月": f"{ret_1m:.1f}%" if ret_1m is not None else "N/A",
            "近3月": f"{ret_3m:.1f}%" if ret_3m is not None else "N/A",
            "近6月": f"{ret_6m:.1f}%" if ret_6m is not None else "N/A",
            "近1年": f"{ret_1y:.1f}%" if ret_1y is not None else "N/A",
        },
    )
