"""基金经理 Agent — 分析基金经理、基金规模、成立时间、费率等"""

from datetime import datetime
from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


def manager_analysis_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """分析基金经理特征: 经理任职、基金规模、成立时间、管理费率"""

    reasons = []
    mgmt_score = 50  # 基础分

    # === 基金经理分析 ===
    has_manager = bool(info and info.manager and info.manager.strip())
    if has_manager:
        mgmt_score += 10
        reasons.append(f"基金经理: {info.manager}")
    else:
        reasons.append("基金经理信息缺失")
        mgmt_score -= 10

    # 基金经理任职起始日期
    if info and info.manager_start:
        try:
            start_dt = datetime.strptime(info.manager_start, "%Y-%m-%d")
            tenure_years = (datetime.now() - start_dt).days / 365.25
            if tenure_years > 3:
                mgmt_score += 15
                reasons.append(f"经理任职{int(tenure_years)}年,经验丰富")
            elif tenure_years > 1:
                mgmt_score += 5
                reasons.append(f"经理任职{tenure_years:.1f}年")
            else:
                mgmt_score -= 5
                reasons.append(f"经理任职不足1年({tenure_years:.1f}年)")
        except ValueError:
            pass

    # === 基金规模分析 ===
    fund_size = info.fund_size if info else None
    if fund_size > 0:
        if fund_size < 0.5:
            mgmt_score -= 10
            reasons.append(f"规模过小({fund_size:.2f}亿),有清盘风险")
        elif fund_size < 2:
            mgmt_score -= 5
            reasons.append(f"规模偏小({fund_size:.2f}亿)")
        elif fund_size > 100:
            mgmt_score += 5
            reasons.append(f"规模较大({fund_size:.0f}亿),流动性好")
        else:
            mgmt_score += 10
            reasons.append(f"规模适中({fund_size:.2f}亿)")
    else:
        reasons.append("规模数据缺失")
        mgmt_score -= 5

    # === 基金成立时间 ===
    if info and info.establish_date:
        try:
            est_dt = datetime.strptime(info.establish_date, "%Y-%m-%d")
            age_years = (datetime.now() - est_dt).days / 365.25
            if age_years < 1:
                mgmt_score -= 15
                reasons.append(f"成立不足1年({age_years:.1f}年),历史业绩短")
            elif age_years < 3:
                mgmt_score -= 5
                reasons.append(f"成立{age_years:.1f}年,历史较短")
            elif age_years > 10:
                mgmt_score += 5
                reasons.append(f"老牌基金,成立{int(age_years)}年")
            else:
                mgmt_score += 10
                reasons.append(f"成立{int(age_years)}年,运作成熟")
        except ValueError:
            pass
    else:
        reasons.append("成立日期缺失")
        mgmt_score -= 5

    # === 管理费率分析 ===
    mgmt_fee = metrics.management_fee
    if mgmt_fee is not None:
        if mgmt_fee < 0.5:
            mgmt_score += 10
            reasons.append(f"管理费率低({mgmt_fee:.2f}%)")
        elif mgmt_fee < 1.0:
            mgmt_score += 5
            reasons.append(f"管理费率较低({mgmt_fee:.2f}%)")
        elif mgmt_fee > 2.0:
            mgmt_score -= 10
            reasons.append(f"管理费率偏高({mgmt_fee:.2f}%)")
        else:
            mgmt_score += 0
            reasons.append(f"管理费率正常({mgmt_fee:.2f}%)")

    # === 基金公司 ===
    if info and info.company:
        mgmt_score += 5
        reasons.append(f"基金公司: {info.company}")

    # 限制在0-100范围
    mgmt_score = max(0, min(100, mgmt_score))

    # === 信号判定 ===
    if mgmt_score >= 65:
        signal = "bullish"
        confidence = min(95, 50 + (mgmt_score - 65) * 1.5)
    elif mgmt_score <= 35:
        signal = "bearish"
        confidence = min(95, 50 + (35 - mgmt_score) * 1.5)
    else:
        signal = "neutral"
        confidence = 50

    return FundSignal(
        signal=signal,
        confidence=round(confidence, 1),
        score=round(mgmt_score, 1),
        reasoning={
            "经理得分": round(mgmt_score, 1),
            "分析要点": reasons,
            "基金经理": info.manager or "未知",
            "经理任期": info.manager_start or "未知",
            "基金规模": f"{fund_size:.2f}亿" if fund_size > 0 else "未知",
            "成立日期": info.establish_date or "未知",
            "管理费率": f"{mgmt_fee:.2f}%" if mgmt_fee else "未知",
            "基金公司": info.company or "未知",
        },
    )
