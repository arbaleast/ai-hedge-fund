"""Analysis business logic — extracted from app/web.py"""
import logging
import sys
import time
from contextlib import redirect_stdout

logger = logging.getLogger(__name__)


# ===== 后端运行函数 =====

def _run_analysis(codes_str: str, months: int, reasoning: bool = False, use_llm: bool = False, backtest: bool = False) -> dict:
    """运行分析并返回结构化数据"""
    codes = [c.strip() for c in codes_str.replace("，", ",").split(",") if c.strip()]
    if not codes:
        return {"error": "请至少输入一个基金代码"}

    from src.main import analyze_fund

    selected_agents = ["trend", "risk", "manager", "valuation", "peer", "holdings"]
    if use_llm:
        selected_agents.append("llm")

    logger.info(f"=== 分析开始 === codes={codes} months={months} reasoning={reasoning} use_llm={use_llm} backtest={backtest} agents={selected_agents}")
    t0 = time.time()

    result = analyze_fund(
        fund_codes=codes,
        months=months,
        show_reasoning=reasoning,
        selected_agents=selected_agents,
        backtest=backtest,
    )

    elapsed = time.time() - t0
    logger.info(f"=== 分析完成 === elapsed={elapsed:.1f}s funds={list(result.get('analyses', {}).keys())}")

    # 转换为可序列化结构
    serialized = {}
    for code, analysis in result["analyses"].items():
        if isinstance(analysis, dict):
            agents_raw = analysis.get("agent_signals", {})
        else:
            agents_raw = analysis.agent_signals if hasattr(analysis, 'agent_signals') else {}

        agents = {}
        for key, sig in agents_raw.items():
            if isinstance(sig, dict):
                raw = sig.get("reasoning") if reasoning else None
                agents[key] = {
                    "signal": sig.get("signal", "neutral"),
                    "confidence": sig.get("confidence", 0),
                    "score": sig.get("score", 0),
                    "reasoning": _format_reasoning(raw),
                }
            else:
                raw = sig.reasoning if reasoning else None
                agents[key] = {
                    "signal": sig.signal,
                    "confidence": sig.confidence,
                    "score": sig.score,
                    "reasoning": _format_reasoning(raw),
                }
        serialized[code] = {
            "code": code,
            "name": analysis.get("name", code) if isinstance(analysis, dict) else (analysis.name or code),
            "agents": agents,
            "summary": result["summary"].get(code, {}),
        }

    serialized["_backtesting"] = _format_backtesting(result.get("backtesting", {}))
    serialized["_nav_history"] = result.get("nav_history", {})

    return serialized


def _format_reasoning(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        lines = []
        for k, v in raw.items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.2f}")
            elif isinstance(v, int):
                lines.append(f"  {k}: {v}")
            elif isinstance(v, list):
                lines.append(f"  {k}:")
                for item in v:
                    lines.append(f"    - {item}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    elif isinstance(raw, str):
        return raw
    return str(raw)


def _format_backtesting(bt_results: dict) -> list:
    """格式化回测结果 — 兼容 backtrader 引擎的 dict 输出

    接收 run_backtest_multi 格式:
        {code: {"code", "name", "strategies": [3个策略结果]}}
    输出扁平化列表 (前端逐行渲染):
        [{code, name, strategy, ...}, ...]
    """
    items = []
    for code, bt in bt_results.items():
        if isinstance(bt, dict) and "strategies" in bt:
            # run_backtest_multi 格式
            fund_name = bt.get("name", code)
            for strat in bt["strategies"]:
                if "error" in strat:
                    items.append({"code": code, "name": fund_name, "error": strat["error"]})
                    continue
                items.append(_format_one_backtest(code, fund_name, strat))
        elif isinstance(bt, dict):
            # 单策略 dict
            items.append(_format_one_backtest(code, bt.get("name", code), bt))
        else:
            # 旧 dataclass 兼容
            items.append({
                "code": code,
                "name": bt.name if hasattr(bt, 'name') else code,
                "total_return_pct": bt.total_return_pct if hasattr(bt, 'total_return_pct') else 0,
                "annualized_return_pct": bt.annualized_return_pct if hasattr(bt, 'annualized_return_pct') else 0,
                "max_drawdown_pct": bt.max_drawdown_pct if hasattr(bt, 'max_drawdown_pct') else 0,
                "sharpe_ratio": bt.sharpe_ratio if hasattr(bt, 'sharpe_ratio') else 0,
                "win_rate": bt.win_rate if hasattr(bt, 'win_rate') else 0,
                "total_trades": bt.total_trades if hasattr(bt, 'total_trades') else 0,
                "buy_and_hold_return_pct": bt.buy_and_hold_return_pct if hasattr(bt, 'buy_and_hold_return_pct') else 0,
                "alpha": bt.alpha if hasattr(bt, 'alpha') else 0,
            })
    return items


def _format_one_backtest(code: str, fund_name: str, bt: dict) -> dict:
    """把单个策略的字典结果序列化为前端字段"""
    return {
        "code": code,
        "name": fund_name,
        "strategy": bt.get("strategy", ""),
        "strategy_name": bt.get("strategy_name", ""),
        "total_return_pct": bt.get("total_return_pct", 0),
        "annualized_return_pct": bt.get("annualized_return_pct", 0),
        "buy_and_hold_return_pct": bt.get("buy_and_hold_return_pct", 0),
        "alpha": bt.get("alpha", 0),
        "max_drawdown_pct": bt.get("max_drawdown_pct", 0),
        "max_drawdown_days": bt.get("max_drawdown_days", 0),
        "sharpe_ratio": bt.get("sharpe_ratio", 0),
        "sqn": bt.get("sqn", 0),
        "win_rate": bt.get("win_rate_pct", 0),
        "total_trades": bt.get("total_trades", 0),
        "winning_trades": bt.get("winning_trades", 0),
        "losing_trades": bt.get("losing_trades", 0),
        "closed_trades": bt.get("closed_trades", 0),
        "start_date": bt.get("start_date", ""),
        "end_date": bt.get("end_date", ""),
        "final_value": bt.get("final_value", 0),
        "trades": bt.get("trades", []),
        "equity_curve": bt.get("equity_curve", []),
    }


# ===== 持久化包装 =====

def _run_and_save(codes_str: str, months: int, reasoning: bool, use_llm: bool, backtest: bool) -> tuple[dict, int]:
    """运行分析 + 保存到 SQLite"""
    result = _run_analysis(codes_str, months, reasoning, use_llm, backtest)
    if "error" not in result:
        try:
            from app.persistence import save_analysis
            codes = [c.strip() for c in codes_str.replace("，", ",").split(",") if c.strip()]
            # 保存时不存 nav_history 节省空间
            saved = {k: v for k, v in result.items() if k != "_nav_history"}
            record_id = save_analysis(codes, saved, months, use_llm, backtest)
            return result, record_id
        except Exception as e:
            print(f"  [WARN] Save to DB failed: {e}", file=sys.stderr)
            return result, 0
    return result, 0
