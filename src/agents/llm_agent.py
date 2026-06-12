"""LLM 分析 Agent — 调用 new-api (deepseek-v4-flash) 做自然语言分析"""

import json
import logging
import os
import time

import httpx

from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav

logger = logging.getLogger("ai_fund.llm")

NEWAPI_URL = os.environ.get("NEWAPI_URL", "http://192.168.98.247:3030/v1/chat/completions")
NEWAPI_KEY = os.environ.get("NEWAPI_KEY", os.environ.get("NEW_API_KEY", "***"))
MODEL = os.environ.get("NEWAPI_MODEL", "deepseek-v4-flash")

SYSTEM_PROMPT = """你是一位专业的基金分析师。你将收到一只中国公募基金的完整数据，包括净值趋势、风险指标、基金经理信息等。

你的任务是从以下维度分析这只基金，输出结构化的评分和信号：

【分析维度】
1. 净值趋势 — 当前价格相对于MA20/MA60/MA120的位置，近期动量方向
2. 风险控制 — 最大回撤是否在合理范围，波动率是否可接受，夏普比率评价
3. 估值水平 — 当前净值在历史中的分位位置，是否处于高估或低估区域
4. 业绩持续性 — 近1月/3月/6月/1年收益是否稳定，各期限表现一致性
5. 基金特征 — 规模、成立年限、费率是否合理
6. 综合判断 — 以上维度的加权汇总

【输出格式】
你必须严格按照以下JSON格式输出（不要包含任何其他文字）：
{
  "signal": "bullish" 或 "neutral" 或 "bearish",
  "score": 0-100的整数,
  "confidence": 0-100的整数,
  "reasoning": {
    "趋势判断": "简短描述",
    "风险评价": "简短描述",
    "估值评价": "简短描述",
    "业绩评价": "简短描述",
    "综合结论": "简短总结"
  }
}

评分标准:
- bullish ≥ 65分: 基金各项指标良好，建议关注或持有
- neutral 36-64分: 基金表现中庸，无明显优势或劣势
- bearish ≤ 35分: 基金面临明显压力，建议谨慎

打分原则:
- 趋势强劲(价格在所有均线上方,各期限正收益) → 高分
- 趋势疲软(价格在所有均线下方,各期限负收益) → 低分
- 估值处于历史低位 → 加分; 估值处于历史高位 → 减分
- 夏普比率高、回撤可控 → 加分
- 规模过小(<0.5亿)或过大(>500亿) → 适当减分
- 持仓过于集中(前3大>60%) → 适当减分（高风险）
- 持仓过于分散(行业<3个) → 适当减分（缺乏专注）
- 机构持有比例高(>50%) → 加分（机构认可）
- 股票仓位与基金类型不匹配（如债券基金高仓位）→ 大幅减分"""


def llm_analysis_agent(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
    start_date: str,
    end_date: str,
    show_reasoning: bool = False,
) -> FundSignal:
    """调用 LLM 对基金进行全面分析"""

    # 构建数据上下文
    fund_data = _build_context(code, name, info, metrics, navs)
    logger.info(f"    → LLM 调用: model={MODEL} prompt_chars={len(SYSTEM_PROMPT) + len(fund_data)} fund={code}")

    try:
        t0 = time.time()
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                NEWAPI_URL,
                headers={"Authorization": f"Bearer {NEWAPI_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": fund_data},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            elapsed = time.time() - t0
            logger.info(f"    → LLM HTTP 响应: status={resp.status_code} elapsed={elapsed:.1f}s")
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            logger.info(f"    → LLM 返回: chars={len(content)} tokens={usage.get('total_tokens', '?')} (prompt={usage.get('prompt_tokens', '?')}, completion={usage.get('completion_tokens', '?')})")

        # 解析 JSON 输出
        parsed = _parse_llm_output(content)
        if parsed is None:
            logger.warning(f"    ⚠ LLM 输出解析失败: content[:200]={content[:200]!r}")
            return FundSignal(
                signal="neutral", confidence=50, score=50,
                reasoning="LLM 返回格式异常",
            )

        logger.info(f"    ✓ LLM 解析成功: signal={parsed.get('signal')} score={parsed.get('score')} confidence={parsed.get('confidence')}")
        return FundSignal(
            signal=parsed.get("signal", "neutral"),
            confidence=parsed.get("confidence", 50),
            score=parsed.get("score", 50),
            reasoning=parsed.get("reasoning", {}),
        )

    except httpx.ConnectError as e:
        logger.error(f"    ✗ LLM 连接失败: {e}")
        return FundSignal(
            signal="neutral", confidence=0, score=0,
            reasoning="无法连接 LLM 服务(new-api)",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"    ✗ LLM HTTP 错误: status={e.response.status_code} body={e.response.text[:200]}")
        return FundSignal(
            signal="neutral", confidence=0, score=0,
            reasoning=f"LLM HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.error(f"    ✗ LLM 调用异常: type={type(e).__name__} msg={e}")
        return FundSignal(
            signal="neutral", confidence=0, score=0,
            reasoning=f"LLM 调用失败: {e}",
        )


def _build_context(
    code: str,
    name: str,
    info: FundInfo,
    metrics: FundMetrics,
    navs: list[FundNav],
) -> str:
    """组装基金数据为 LLM 可读的上下文"""
    lines = [f"基金代码: {code}", f"基金名称: {name}"]

    if info:
        lines.extend([
            f"基金类型: {info.type or '未知'}",
            f"基金经理: {info.manager or '未知'}",
            f"基金公司: {info.company or '未知'}",
            f"成立日期: {info.establish_date or '未知'}",
            f"基金规模: {info.fund_size:.2f}亿" if info.fund_size else "基金规模: 未知",
        ])

    if metrics:
        lines.extend([
            f"\n[收益指标]",
            f"最新净值: {metrics.latest_nav:.4f} (日期: {metrics.latest_date})",
            f"近1月: {metrics.return_1m or 0:.2f}%",
            f"近3月: {metrics.return_3m or 0:.2f}%",
            f"近6月: {metrics.return_6m or 0:.2f}%",
            f"近1年: {metrics.return_1y or 0:.2f}%",
            f"\n[风险指标]",
            f"近1年最大回撤: {metrics.max_drawdown_1y or 0:.2f}%",
            f"年化波动率: {metrics.volatility_1y or 0:.2f}%",
            f"夏普比率: {metrics.sharpe_ratio or 0:.2f}",
        ])

        # === 持仓数据（关键 — 帮助 LLM 理解基金风格）===
        if metrics.top_holdings:
            lines.append("\n[前十大重仓股]")
            for h in metrics.top_holdings[:10]:
                if h.ratio > 0:
                    lines.append(f"  - {h.name or h.code}: {h.ratio:.2f}%")
                else:
                    lines.append(f"  - {h.name or h.code}")
            if metrics.stock_position_ratio is not None:
                lines.append(f"\n  股票总仓位: {metrics.stock_position_ratio:.1f}%")

        if metrics.sector_allocation:
            lines.append("\n[行业/板块分布]")
            for sec, n in metrics.sector_allocation.items():
                if n > 0:
                    lines.append(f"  - {sec}: {n} 只")

        if metrics.asset_allocation:
            lines.append("\n[资产配置]")
            for k, v in metrics.asset_allocation.items():
                if v:
                    latest = list(v.values())[-1] if v else None
                    if latest is not None:
                        lines.append(f"  - {k}: {latest:.2f}%")

        if metrics.holder_structure:
            lines.append("\n[持有人结构]")
            for k, v in metrics.holder_structure.items():
                if v:
                    latest = list(v.values())[-1] if v else None
                    if latest is not None:
                        lines.append(f"  - {k}: {latest:.2f}%")

    if navs and len(navs) >= 120:
        nav_values = [n.nav for n in navs]
        import numpy as np
        arr = np.array(nav_values)
        current = arr[-1]
        ma20 = np.mean(arr[-20:]) if len(arr) >= 20 else current
        ma60 = np.mean(arr[-60:]) if len(arr) >= 60 else current
        ma120 = np.mean(arr[-120:]) if len(arr) >= 120 else current
        hist_high = float(np.max(arr))
        hist_low = float(np.min(arr))
        hist_mean = float(np.mean(arr))
        pct = (current - hist_low) / (hist_high - hist_low) * 100 if hist_high > hist_low else 50

        lines.extend([
            f"\n[技术指标]",
            f"现价: {current:.4f}",
            f"MA20: {ma20:.4f}",
            f"MA60: {ma60:.4f}",
            f"MA120: {ma120:.4f}",
            f"历史高点: {hist_high:.4f}",
            f"历史低点: {hist_low:.4f}",
            f"历史均值: {hist_mean:.4f}",
            f"历史分位: {pct:.1f}%",
        ])

    return "\n".join(lines)


def _parse_llm_output(content: str) -> dict | None:
    """从 LLM 回复中提取 JSON"""
    # 尝试直接解析
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ```
    import re
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... }
    m = re.search(r'\{.*\}', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None
