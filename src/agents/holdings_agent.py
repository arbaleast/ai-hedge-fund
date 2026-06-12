"""持仓分析 Agent — 分析基金持仓集中度、行业分布、风格特征"""

from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


def holdings_analysis_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """分析基金持仓结构：集中度、行业分布、风格特征"""
    score = 50
    signal = "neutral"
    confidence = 50
    reasons = {}

    # ── 1. 持仓集中度分析 ──
    holdings = metrics.top_holdings if metrics else []
    n_holdings = len(holdings)
    total_ratio = sum(h.ratio for h in holdings if h.ratio > 0)

    if n_holdings == 0:
        reasons["持仓覆盖"] = "无持仓数据，无法分析"
        concentration_score = 50
    else:
        # 前3大集中度
        top3 = sorted(holdings, key=lambda h: h.ratio, reverse=True)[:3]
        top3_ratio = sum(h.ratio for h in top3)
        has_ratios = any(h.ratio > 0 for h in holdings)

        if has_ratios:
            if top3_ratio > 60:
                concentration_score = 35  # 过度集中
                reasons["持仓集中度"] = f"前3大持仓占比 {top3_ratio:.1f}%，集中度偏高，单只股票风险较大"
            elif top3_ratio > 40:
                concentration_score = 50  # 适中
                reasons["持仓集中度"] = f"前3大持仓占比 {top3_ratio:.1f}%，集中度适中"
            elif top3_ratio > 0:
                concentration_score = 65  # 分散
                reasons["持仓集中度"] = f"前3大持仓占比 {top3_ratio:.1f}%，较为分散，风险可控"
            else:
                concentration_score = 50
                reasons["持仓集中度"] = "持仓比例数据不可用"
        else:
            concentration_score = 50
            reasons["持仓集中度"] = f"持有 {n_holdings} 只股票（比例数据暂不可用）"

    # ── 2. 行业分布分析 ──
    sector = metrics.sector_allocation if metrics else {}
    if sector:
        top_sector = max(sector, key=lambda k: sector[k]) if sector else "其他"
        top_ratio = sector[top_sector] / max(sum(sector.values()), 1) * 100 if sum(sector.values()) > 0 else 0
        n_sectors = len(sector)

        if n_sectors >= 5:
            sector_score = 65  # 行业分散
            reasons["行业分布"] = f"覆盖 {n_sectors} 个行业，最集中为 {top_sector} ({top_ratio:.0f}%)，行业较分散"
        elif n_sectors >= 3:
            sector_score = 50
            reasons["行业分布"] = f"覆盖 {n_sectors} 个行业，最集中为 {top_sector} ({top_ratio:.0f}%)"
        else:
            sector_score = 35
            reasons["行业分布"] = f"仅覆盖 {n_sectors} 个行业，高度集中在 {top_sector} ({top_ratio:.0f}%)"
    else:
        sector_score = 50
        reasons["行业分布"] = "行业分布数据不可用"

    # ── 3. 资产配置分析 ──
    aa = metrics.asset_allocation if metrics else {}
    stock_ratio = metrics.stock_position_ratio

    if stock_ratio is not None:
        if info and info.type:
            ftype = info.type or ""
            if "债券" in ftype or "货" in ftype:
                # 债券型/货币型 — 股票仓位应低
                if stock_ratio < 20:
                    alloc_score = 70
                else:
                    alloc_score = 40
                    reasons["资产配置"] = f"{ftype}基金股票仓位 {stock_ratio:.1f}%，与产品定位不符"
            elif "指数" in ftype:
                alloc_score = 60  # 指数基金基本满仓
            else:
                # 混合型/股票型
                if 70 <= stock_ratio <= 95:
                    alloc_score = 65  # 积极型合理仓位
                elif stock_ratio < 60:
                    alloc_score = 45  # 仓位偏低
                else:
                    alloc_score = 55
                reasons["资产配置"] = f"股票仓位 {stock_ratio:.1f}%"
        else:
            alloc_score = 55
            reasons["资产配置"] = f"股票仓位 {stock_ratio:.1f}%"
    else:
        alloc_score = 50
        reasons["资产配置"] = "仓位数据不可用"

    # ── 4. 持有人结构分析 ──
    hs = metrics.holder_structure if metrics else {}
    if hs:
        inst = hs.get("机构持有比例", {})
        if inst:
            latest_inst = list(inst.values())[-1] if inst.values() else None
            if latest_inst is not None:
                if latest_inst > 50:
                    # 机构持有为主 — 说明机构认可度高
                    hs_score = 65
                    reasons["持有人结构"] = f"机构持有 {latest_inst:.1f}%，机构认可度高"
                elif latest_inst > 20:
                    hs_score = 55
                    reasons["持有人结构"] = f"机构持有 {latest_inst:.1f}%，机构/个人比例均衡"
                else:
                    hs_score = 45
                    reasons["持有人结构"] = f"机构持有 {latest_inst:.1f}%，散户主导，需关注持有人稳定性"
            else:
                hs_score = 50
        else:
            hs_score = 50
    else:
        hs_score = 50

    # ── 综合评分 ──
    weights = {"concentration": 0.30, "sector": 0.25, "allocation": 0.25, "holders": 0.20}

    # 检查是否有足够的数据给出有意义的评分
    has_data = bool(holdings) or (stock_ratio is not None) or bool(sector)

    if not has_data:
        return FundSignal(
            signal="neutral", confidence=20, score=50,
            reasoning="持仓数据不足，无法进行持仓分析",
        )

    final_score = (
        concentration_score * weights["concentration"]
        + sector_score * weights["sector"]
        + alloc_score * weights["allocation"]
        + hs_score * weights["holders"]
    )

    final_score = max(0, min(100, final_score))

    if final_score >= 65:
        signal = "bullish"
        confidence = min(80, int(final_score * 0.9))
    elif final_score <= 35:
        signal = "bearish"
        confidence = min(80, int((100 - final_score) * 0.8))
    else:
        signal = "neutral"
        confidence = 55

    reasoning_text = "-----------------------------\n"
    for k, v in reasons.items():
        reasoning_text += f"  {k}: {v}\n"
    reasoning_text += f"  综合评分: {final_score:.0f}/100"

    return FundSignal(
        signal=signal,
        score=round(final_score),
        confidence=min(100, confidence),
        reasoning=reasoning_text if show_reasoning else None,
    )
