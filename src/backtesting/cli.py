#!/usr/bin/env python3
"""AI 基金分析系统 — 回测 CLI"""

import argparse
import sys
from datetime import datetime, timedelta

from src.tools.api import fetch_fund_info, fetch_nav_history
from src.backtesting.engine import run_backtest
from src.backtesting.strategy import sma_crossover_strategy, trend_following_strategy


def main():
    parser = argparse.ArgumentParser(description="基金回测工具")
    parser.add_argument("codes", nargs="+", help="基金代码")
    parser.add_argument("--capital", type=float, default=100000, help="初始资金")
    parser.add_argument("--months", type=int, default=24, help="回测周期（月）")
    parser.add_argument("--strategy", choices=["sma", "trend"], default="sma",
                        help="策略: sma(均线交叉), trend(趋势跟踪)")
    args = parser.parse_args()

    if args.strategy == "sma":
        strategy_fn = sma_crossover_strategy(short_window=20, long_window=60)
    else:
        strategy_fn = trend_following_strategy(buy_threshold=55, sell_threshold=45)

    results = []
    for code in args.codes:
        print(f"获取 {code} 数据...")
        info = fetch_fund_info(code)
        navs = fetch_nav_history(code, months=args.months)
        if not navs or len(navs) < 60:
            print(f"  {code}: 数据不足，跳过")
            continue

        name = info.name if info and info.name else code
        result = run_backtest(code, name, navs, strategy_fn,
                              initial_capital=args.capital)
        results.append(result)
        print()
        print(result.summary)
        print()

    if len(results) > 1:
        print("=" * 60)
        print("排名 (按夏普比率)")
        for i, r in enumerate(sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)):
            print(f"  {i+1}. {r.code} {r.name}: "
                  f"收益{r.total_return_pct:+.2f}% | "
                  f"夏普{r.sharpe_ratio:.2f} | "
                  f"回撤{r.max_drawdown_pct:.1f}% | "
                  f"超额{r.alpha:+.2f}%")


if __name__ == "__main__":
    main()
