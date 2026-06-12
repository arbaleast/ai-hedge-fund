"""基金分析显示工具 — 替代原股票交易显示"""

from colorama import Fore, Style
from tabulate import tabulate
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


# Agent显示名称映射
AGENT_DISPLAY_NAMES = {
    "trend": "趋势分析",
    "risk": "风险分析",
    "manager": "经理分析",
    "valuation": "估值分析",
    "peer": "同类对比",
    "llm": "LLM 分析",
    "holdings": "持仓分析",
}


def _get(d, key, default=None):
    """从 dict 或 object 安全取值"""
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)


def print_fund_analysis(result: dict, show_reasoning: bool = False) -> None:
    """打印基金分析结果

    Args:
        result: analyze_fund()返回的结果字典
        show_reasoning: 是否显示详细推理过程
    """
    analyses = result.get("analyses", {})
    summary = result.get("summary", {})

    if not analyses:
        print(f"{Fore.RED}没有分析结果{Style.RESET_ALL}")
        return

    console = Console()

    for code, analysis in analyses.items():
        if isinstance(analysis, dict):
            name = analysis.get("name", code)
            signals = analysis.get("agent_signals", {})
        else:
            name = analysis.name or code
            signals = analysis.agent_signals if hasattr(analysis, 'agent_signals') else {}

        fund_summary = summary.get(code, {})

        # === 标题 ===
        final_signal = fund_summary.get("final_signal", "neutral")
        score = fund_summary.get("score", 0)

        signal_color = {
            "bullish": Fore.GREEN,
            "bearish": Fore.RED,
            "neutral": Fore.YELLOW,
        }.get(final_signal, Fore.WHITE)

        signal_text = {
            "bullish": "看多",
            "bearish": "看空",
            "neutral": "中性",
        }.get(final_signal, "未知")

        print(f"\n{'=' * 60}")
        print(f"{Fore.CYAN}{Style.BRIGHT}基金: {name}({code}){Style.RESET_ALL}")
        print(f"{signal_color}信号: {signal_text} | {Fore.WHITE}综合评分: {score:.1f} | "
              f"置信度: {fund_summary.get('confidence', 0):.0f}%{Style.RESET_ALL}")
        print(f"{Fore.WHITE}看多Agent: {Fore.GREEN}{fund_summary.get('bullish_agents', 0)}"
              f"{Style.RESET_ALL} | "
              f"{Fore.WHITE}看空Agent: {Fore.RED}{fund_summary.get('bearish_agents', 0)}"
              f"{Style.RESET_ALL}")
        print(f"{'=' * 60}")

        # === Agent信号表格 ===
        if not signals:
            print(f"{Fore.YELLOW}无Agent信号数据{Style.RESET_ALL}")
            continue

        table_data = []
        for agent_key, signal in signals.items():
            display_name = AGENT_DISPLAY_NAMES.get(agent_key, agent_key)
            sig = _get(signal, "signal", "neutral")
            sig_score = _get(signal, "score", 0)
            sig_conf = _get(signal, "confidence", 0)
            sig_color = {"bullish": Fore.GREEN, "bearish": Fore.RED, "neutral": Fore.YELLOW}

            table_data.append([
                f"{Fore.CYAN}{display_name}{Style.RESET_ALL}",
                f"{sig_color.get(sig, Fore.WHITE)}{sig.upper():8s}{Style.RESET_ALL}",
                f"{Fore.WHITE}{sig_score:5.1f}{Style.RESET_ALL}",
                f"{Fore.WHITE}{sig_conf:5.1f}%{Style.RESET_ALL}",
            ])

        print(f"\n{Fore.WHITE}{Style.BRIGHT}Agent分析结果:{Style.RESET_ALL}")
        print(tabulate(
            table_data,
            headers=[f"{Fore.WHITE}Agent", "信号", "评分", "置信度"],
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        ))

        # === 详细推理过程 ===
        if show_reasoning:
            print(f"\n{Fore.WHITE}{Style.BRIGHT}详细推理:{Style.RESET_ALL}")
            for agent_key, signal in signals.items():
                display_name = AGENT_DISPLAY_NAMES.get(agent_key, agent_key)
                reasoning = _get(signal, "reasoning")

                if isinstance(reasoning, dict):
                    content_lines = []
                    for k, v in reasoning.items():
                        if isinstance(v, list):
                            content_lines.append(f"  {k}:")
                            for item in v:
                                content_lines.append(f"    - {item}")
                        elif v is not None:
                            content_lines.append(f"  {k}: {v}")
                    content = "\n".join(content_lines)
                elif isinstance(reasoning, str):
                    content = reasoning
                else:
                    content = str(reasoning) if reasoning else "无"

                console.print(Panel(
                    content,
                    title=f"[bold]{display_name}[/bold]",
                    border_style="cyan",
                ))

        print()


def print_single_fund(code: str, name: str, signal: dict, show_reasoning: bool = False) -> None:
    """打印单只基金的单Agent分析结果 (用于调试)"""
    sig = _get(signal, "signal", "neutral")
    sig_color = {"bullish": Fore.GREEN, "bearish": Fore.RED, "neutral": Fore.YELLOW}
    sig_text = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}.get(sig, "未知")

    print(f"\n{Fore.CYAN}基金: {name}({code}){Style.RESET_ALL}")
    print(f"{sig_color}信号: {sig_text} | "
          f"{Fore.WHITE}评分: {_get(signal, 'score', 0):.1f} | "
          f"置信度: {_get(signal, 'confidence', 0):.1f}%{Style.RESET_ALL}")

    if show_reasoning:
        reasoning = _get(signal, "reasoning", {})
        if isinstance(reasoning, dict):
            for k, v in reasoning.items():
                if v is not None:
                    print(f"  {k}: {v}")
