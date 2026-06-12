#!/usr/bin/env python3
"""AI 基金分析系统 — LangGraph 编排版"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from colorama import Fore, Style, init
from langgraph.graph import END, StateGraph

from src.agents.trend_agent import trend_analysis_agent
from src.agents.risk_agent import risk_analysis_agent
from src.agents.manager_agent import manager_analysis_agent
from src.agents.valuation_agent import fund_valuation_agent
from src.agents.peer_agent import peer_comparison_agent
from src.agents.llm_agent import llm_analysis_agent
from src.agents.holdings_agent import holdings_analysis_agent

from src.data.models import FundSignal, FundAnalysis, FundNav, FundMetrics
from src.graph.state import AgentState, FundData
from src.tools.api import fetch_fund_info, fetch_fund_metrics, fetch_latest_nav, fetch_nav_history
from src.utils.display import print_fund_analysis

# ===== 日志 =====
logger = logging.getLogger("ai_fund")
# 不重新配置 — 由 web.py 初始化

init(autoreset=True)

AGENT_REGISTRY = {
    "trend":       {"name": "趋势分析 Agent",      "func": trend_analysis_agent,       "state_key": "signal_trend"},
    "risk":        {"name": "风险分析 Agent",      "func": risk_analysis_agent,        "state_key": "signal_risk"},
    "manager":     {"name": "基金经理 Agent",       "func": manager_analysis_agent,     "state_key": "signal_manager"},
    "valuation":   {"name": "估值分析 Agent",      "func": fund_valuation_agent,       "state_key": "signal_valuation"},
    "peer":        {"name": "同类对比 Agent",      "func": peer_comparison_agent,      "state_key": "signal_peer"},
    "llm":         {"name": "LLM 深度分析 Agent", "func": llm_analysis_agent,         "state_key": "signal_llm"},
    "holdings":    {"name": "持仓分析 Agent",      "func": holdings_analysis_agent,    "state_key": "signal_holdings"},
}

ALL_AGENTS = list(AGENT_REGISTRY.keys())

AGENT_FIELD_MAP = {info["state_key"]: key for key, info in AGENT_REGISTRY.items()}


# ===== LangGraph Nodes =====

def start_node(state: AgentState) -> dict:
    """初始化：加载基金数据"""
    if not state.remaining_codes:
        return {"current_code": "", "current_fund": None}

    code = state.remaining_codes[0]
    months = 24
    logger.info(f"  → start_node: 加载基金 {code} (剩余 {len(state.remaining_codes)} 只)")

    info = fetch_fund_info(code)
    latest = fetch_latest_nav(code)
    metrics = fetch_fund_metrics(code, months=months)
    navs = fetch_nav_history(code, months=months)

    name = info.name if info and info.name else (latest.get("name", code) if latest else code)
    logger.info(f"  → 基金 {code} 数据加载完成: name={name} navs={len(navs) if navs else 0}")

    # Reset agent signal fields for this fund
    reset = {info["state_key"]: None for info in AGENT_REGISTRY.values()}

    return {
        "current_code": code,
        "remaining_codes": state.remaining_codes[1:],
        "current_fund": FundData(
            code=code, name=name,
            info=info, metrics=metrics,
            navs=navs,
            start_date=(datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d"),
            end_date=datetime.now().strftime("%Y-%m-%d"),
        ),
        **reset,
    }


def _make_agent_node(agent_key: str):
    """生成 Agent Node — 每个 Agent 有独立的状态字段"""
    info = AGENT_REGISTRY[agent_key]
    state_key = info["state_key"]
    func = info["func"]

    def node_fn(state: AgentState) -> dict:
        fund = state.current_fund
        if not fund or not fund.navs:
            logger.warning(f"  ⚠ {agent_key} agent: 跳过 (无 fund/navs 数据)")
            return {state_key: None}

        logger.info(f"  • {agent_key} agent: 开始分析 {fund.code} ({fund.name})")
        t0 = time.time()

        signal = func(
            code=fund.code, name=fund.name,
            info=fund.info, metrics=fund.metrics,
            navs=fund.navs,
            start_date=fund.start_date, end_date=fund.end_date,
            show_reasoning=state.show_reasoning,
        )

        elapsed = time.time() - t0
        logger.info(f"  ✓ {agent_key} agent 完成: {fund.code} signal={signal.signal} score={signal.score} confidence={signal.confidence}% ({elapsed:.1f}s)")

        return {state_key: {
            "signal": signal.signal,
            "score": signal.score,
            "confidence": signal.confidence,
            "reasoning": signal.reasoning if state.show_reasoning else None,
        }}

    return node_fn


def aggregator_node(state: AgentState) -> dict:
    """汇总所有 Agent 信号，生成综合评分"""
    fund = state.current_fund
    if not fund:
        return {}

    # Collect signals from all agent fields
    signals = {}
    total_score = 0
    bullish_count = 0
    bearish_count = 0
    n = 0

    for agent_key, info in AGENT_REGISTRY.items():
        sig = getattr(state, info["state_key"], None)
        if sig is None:
            continue
        signals[agent_key] = sig
        total_score += sig.get("score", 0)
        if sig.get("signal") == "bullish":
            bullish_count += 1
        elif sig.get("signal") == "bearish":
            bearish_count += 1
        n += 1

    avg_score = round(total_score / n, 1) if n > 0 else 0

    if avg_score >= 70:
        final_signal = "bullish"
    elif avg_score <= 35:
        final_signal = "bearish"
    else:
        final_signal = "neutral"

    confidence = round(max(bullish_count, bearish_count) / max(n, 1) * 100)

    analysis = FundAnalysis(
        code=fund.code,
        name=fund.name,
        final_signal=final_signal,
        score=avg_score,
        confidence=confidence,
        agent_signals={k: FundSignal(
            signal=v["signal"], score=v["score"],
            confidence=v["confidence"],
            reasoning=v.get("reasoning"),
        ) for k, v in signals.items()},
        summary={k: {
            "signal": v["signal"],
            "score": v["score"],
            "confidence": v["confidence"],
        } for k, v in signals.items()},
    )

    new_results = dict(state.fund_results)
    new_results[fund.code] = analysis.model_dump()
    new_completed = list(state.completed_codes)
    new_completed.append(fund.code)

    return {
        "fund_results": new_results,
        "completed_codes": new_completed,
        "current_fund": None,
        "current_code": "",
    }


def should_continue(state: AgentState) -> str:
    """路由：继续分析下一只或结束"""
    return "next" if state.remaining_codes else "end"


# ===== Workflow Builder =====

def create_workflow(selected_agents: Optional[list[str]] = None):
    """创建 LangGraph 工作流 — 所有 Agent 并行执行"""
    agents = selected_agents if selected_agents else ALL_AGENTS

    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start_node)
    workflow.set_entry_point("start_node")

    # Add selected agent nodes (each can write to its own field in parallel)
    for agent_key in agents:
        if agent_key in AGENT_REGISTRY:
            workflow.add_node(f"agent_{agent_key}", _make_agent_node(agent_key))
            workflow.add_edge("start_node", f"agent_{agent_key}")

    # Aggregator
    workflow.add_node("aggregator", aggregator_node)

    # All agents → aggregator (parallel fan-in)
    for agent_key in agents:
        if agent_key in AGENT_REGISTRY:
            workflow.add_edge(f"agent_{agent_key}", "aggregator")

    # Loop: aggregator → start_node or END
    workflow.add_conditional_edges(
        "aggregator",
        should_continue,
        {"next": "start_node", "end": END},
    )

    return workflow


# ===== 主入口 =====

def analyze_fund(
    fund_codes: list[str],
    months: int = 24,
    show_reasoning: bool = False,
    selected_agents: Optional[list[str]] = None,
    backtest: bool = False,
    backtest_strategy: str = "sma",
    backtest_capital: float = 100000.0,
    model_name: str = "deepseek-chat",
    model_provider: str = "OpenAI",
) -> dict:
    """运行 LangGraph 编排的基金分析"""
    agents = selected_agents if selected_agents else ALL_AGENTS
    logger.info(f"analyze_fund START codes={fund_codes} months={months} agents={agents} backtest={backtest} use_llm={'llm' in agents}")

    workflow = create_workflow(agents)
    agent = workflow.compile()

    initial_state = AgentState(
        remaining_codes=list(fund_codes),
        show_reasoning=show_reasoning,
        use_llm="llm" in agents,
    )

    final_state_dict = agent.invoke(initial_state)
    final_state = AgentState(**final_state_dict)
    logger.info(f"analyze_fund WORKFLOW 完成 funds={list(final_state.fund_results.keys())}")

    result = {
        "analyses": _analyses_to_dict(final_state.fund_results),
        "summary": _generate_summary(final_state.fund_results),
        "nav_history": _collect_nav_history(fund_codes, months),
    }

    # 回测 — backtrader 引擎, 同时跑全部 3 策略
    if backtest and final_state.fund_results:
        from src.backtesting.bt_engine import run_backtest_multi
        bt_results = {}
        for code in final_state.fund_results:
            navs = fetch_nav_history(code, months=months)
            if len(navs) < 60:
                continue
            info = fetch_fund_info(code)
            name = info.name if info and info.name else code
            try:
                bt_results[code] = run_backtest_multi(
                    code=code, name=name, navs=navs,
                    initial_capital=backtest_capital,
                )
            except Exception as e:
                logger.error(f"  ✗ 回测失败 {code}: {e}")
        result["backtesting"] = bt_results

    return result


def _analyses_to_dict(analyses: dict[str, Any]) -> dict[str, Any]:
    """确保 analyses 中的值是 dict（兼容 model_dump 输出）"""
    result = {}
    for code, val in analyses.items():
        if isinstance(val, dict):
            result[code] = val
        elif hasattr(val, "model_dump"):
            result[code] = val.model_dump()
        else:
            result[code] = val
    return result


def _collect_nav_history(fund_codes: list[str], months: int) -> dict[str, list[dict]]:
    """收集所有基金的净值历史 — 用于 Web UI 走势图叠加"""
    history = {}
    for code in fund_codes:
        try:
            navs = fetch_nav_history(code, months=months)
            history[code] = [{"date": n.date, "nav": n.nav} for n in navs]
        except Exception:
            history[code] = []
    return history


def _generate_summary(analyses: dict[str, Any]) -> dict:
    """生成汇总评分"""
    summary = {}
    for code, analysis_dict in analyses.items():
        signals = analysis_dict.get("agent_signals", {})
        if not signals:
            continue

        total_score = 0
        bullish_count = 0
        bearish_count = 0

        for agent_key, signal in signals.items():
            if isinstance(signal, dict):
                total_score += signal.get("score", 0)
                if signal.get("signal") == "bullish":
                    bullish_count += 1
                elif signal.get("signal") == "bearish":
                    bearish_count += 1

        n = len(signals)
        avg_score = round(total_score / n, 1) if n > 0 else 0

        if avg_score >= 70:
            final_signal = "bullish"
        elif avg_score <= 35:
            final_signal = "bearish"
        else:
            final_signal = "neutral"

        confidence = round(max(bullish_count, bearish_count) / max(n, 1) * 100)

        summary[code] = {
            "name": analysis_dict.get("name", ""),
            "final_signal": final_signal,
            "score": avg_score,
            "confidence": confidence,
            "bullish_agents": bullish_count,
            "bearish_agents": bearish_count,
            "total_agents": n,
        }
    return summary
