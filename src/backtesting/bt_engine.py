"""
回测引擎 — 基于 backtrader 的基金净值回测

支持:
  - 三种策略: SMA 交叉 / 趋势跟踪 / 买入持有
  - 5 个内置 analyzer: Sharpe, DrawDown, TradeAnalyzer, TimeReturn, SQN
  - 自定义数据源 (从 FundNav list 喂入)
  - 标准化的 JSON 输出 (供 Web UI 渲染)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import backtrader as bt

from src.data.models import FundNav

logger = logging.getLogger("ai_fund.bt")

# ===== 自定义数据源 =====

class FundNavData(bt.feeds.PandasData):
    """
    从 list[FundNav] 构造 backtrader 数据源 — 通过临时 DataFrame
    - 用 nav (单位净值) 作为 close
    - 用 acc_nav (累计净值) 作为 adjclose
    - 日线级别
    """
    # 添加 adjclose line (PandasData 默认没有)
    lines = ('adjclose',)

    # 参数: 我们的列名 → backtrader lines
    params = (
        ('datetime', 'date'),
        ('close', 'nav'),
        ('adjclose', 'acc_nav'),
        # OHLCV 没用到, 给占位符 (PandasData 内部会处理)
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('volume', 'volume'),
        ('openinterest', None),
    )


def _navs_to_dataframe(navs: list[FundNav]):
    """
    把 list[FundNav] 转为 backtrader 兼容的 pandas DataFrame
    - date 列必须是 datetime 类型 (backtrader 要求)
    - 必须有 datetime index 或 'date' 列
    """
    import pandas as pd

    if not navs:
        raise ValueError("净值列表为空")

    df = pd.DataFrame([
        {
            'date': pd.to_datetime(n.date),
            'nav': n.nav,
            'acc_nav': n.acc_nav if n.acc_nav is not None else n.nav,
            # 占位列, 防止 backtrader 警告
            'open': n.nav,
            'high': n.nav,
            'low': n.nav,
            'volume': 0.0,
        }
        for n in navs
    ])
    df = df.sort_values('date').reset_index(drop=True)
    return df


# ===== 策略 =====

class SMAStrategy(bt.Strategy):
    """
    简单均线交叉策略
    - 短均线上穿长均线 → 全仓买入
    - 短均线下穿长均线 → 清仓卖出
    """
    params = (
        ('short_period', 20),
        ('long_period', 60),
        ('printlog', False),
    )

    def __init__(self):
        self.sma_short = bt.ind.SMA(period=self.p.short_period)
        self.sma_long = bt.ind.SMA(period=self.p.long_period)
        self.crossover = bt.ind.CrossOver(self.sma_short, self.sma_long)
        self.order = None
        self.trade_count = 0
        self.win_count = 0
        self.trade_list: list[dict] = []

    def next(self):
        if self.order:
            return
        if not self.position:
            if self.crossover > 0:  # 金叉
                self.order = self.buy()
        else:
            if self.crossover < 0:  # 死叉
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.trade_count += 1
            if self.p.printlog:
                direction = "BUY" if order.isbuy() else "SELL"
                logger.info(f"  [SMA] {direction} executed: {bt.num2date(order.executed.dt).date()} "
                           f"price={order.executed.price:.4f} size={order.executed.size:.0f}")
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            if trade.pnl > 0:
                self.win_count += 1
            self.trade_list.append({
                "open_dt": bt.num2date(trade.dtopen).isoformat(),
                "close_dt": bt.num2date(trade.dtclose).isoformat(),
                "pnl": round(trade.pnlcomm, 2),
                "pnl_pct": round(trade.pnlcomm / (trade.price * abs(trade.size)) * 100, 2) if trade.size else 0,
            })


class TrendStrategy(bt.Strategy):
    """
    趋势跟踪策略
    - 短期价格上涨 + 上涨日数占比 >= 65% → 买入
    - 短期价格下跌 + 上涨日数占比 <= 35% → 卖出
    """
    params = (
        ('lookback', 20),
        ('up_threshold', 0.65),
        ('down_threshold', 0.35),
    )

    def __init__(self):
        self.order = None
        self.prices = self.data.close
        self.up_days = 0
        self.lookback = self.p.lookback
        self.trade_count = 0
        self.win_count = 0
        self.trade_list: list[dict] = []

    def next(self):
        if self.order or len(self) < self.lookback + 1:
            return

        # 计算 lookback 窗口内上涨天数
        up_count = 0
        for i in range(1, self.lookback + 1):
            if self.prices[0 - i] > self.prices[0 - i - 1]:
                up_count += 1
        up_ratio = up_count / self.lookback
        change_pct = (self.prices[0] - self.prices[-self.lookback]) / self.prices[-self.lookback] * 100

        if not self.position:
            if up_ratio >= self.p.up_threshold and change_pct > 0:
                self.order = self.buy()
        else:
            if up_ratio <= self.p.down_threshold and change_pct < -2.0:
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.trade_count += 1
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            if trade.pnl > 0:
                self.win_count += 1
            self.trade_list.append({
                "open_dt": bt.num2date(trade.dtopen).isoformat(),
                "close_dt": bt.num2date(trade.dtclose).isoformat(),
                "pnl": round(trade.pnlcomm, 2),
                "pnl_pct": round(trade.pnlcomm / (trade.price * abs(trade.size)) * 100, 2) if trade.size else 0,
            })


class HoldStrategy(bt.Strategy):
    """
    买入持有基准 — 第一个 bar 全仓买入, 持有到期末
    """
    def __init__(self):
        self.order = None
        self.bought = False
        self.trade_count = 0
        self.win_count = 0
        self.trade_list: list[dict] = []

    def next(self):
        if not self.bought:
            self.order = self.buy()
            self.bought = True

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.trade_count += 1
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            if trade.pnl > 0:
                self.win_count += 1
            self.trade_list.append({
                "open_dt": bt.num2date(trade.dtopen).isoformat(),
                "close_dt": bt.num2date(trade.dtclose).isoformat(),
                "pnl": round(trade.pnlcomm, 2),
                "pnl_pct": round(trade.pnlcomm / (trade.price * abs(trade.size)) * 100, 2) if trade.size else 0,
            })


# ===== 策略注册表 =====

STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {
    "sma": {
        "name": "SMA 交叉",
        "cls": SMAStrategy,
        "default_params": {"short_period": 20, "long_period": 60},
    },
    "trend": {
        "name": "趋势跟踪",
        "cls": TrendStrategy,
        "default_params": {"lookback": 20, "up_threshold": 0.65, "down_threshold": 0.35},
    },
    "hold": {
        "name": "买入持有 (基准)",
        "cls": HoldStrategy,
        "default_params": {},
    },
}


# ===== 主入口 =====

def run_backtest(
    code: str,
    name: str,
    navs: list[FundNav],
    strategy_name: str = "sma",
    initial_capital: float = 100000.0,
    commission_pct: float = 0.001,
    strategy_params: Optional[dict] = None,
) -> dict:
    """
    运行回测, 返回 JSON 可序列化的字典

    Returns:
        {
            "code": "019305",
            "name": "摩根标普500",
            "strategy": "sma",
            "strategy_name": "SMA 交叉",
            "start_date": "2023-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "final_value": 115000,
            "total_return_pct": 15.0,
            "annualized_return_pct": 7.2,
            "buy_and_hold_return_pct": 12.0,
            "alpha": 3.0,
            "max_drawdown_pct": -8.5,
            "sharpe_ratio": 1.25,
            "sqn": 1.8,
            "total_trades": 12,
            "winning_trades": 8,
            "win_rate_pct": 66.7,
            "trades": [...],
            "equity_curve": [{"date": "...", "value": ..., "benchmark_value": ...}, ...]
        }
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知策略: {strategy_name}. 可选: {list(STRATEGY_REGISTRY.keys())}")

    if len(navs) < 60:
        raise ValueError(f"历史净值数据不足 ({len(navs)}条, 至少需要60条)")

    navs_sorted = sorted(navs, key=lambda n: n.date)
    start_date = navs_sorted[0].date
    end_date = navs_sorted[-1].date

    logger.info(f"回测开始: {code} {name} strategy={strategy_name} navs={len(navs_sorted)} {start_date}→{end_date}")

    # ---- 构建 backtrader engine ----
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(initial_capital)
    cerebro.broker.setcommission(commission=commission_pct)

    # 仓位控制: 全仓买入 (single asset, all-in/out)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)  # 留 5% 给手续费缓冲

    # 数据源 — 用 PandasData (基于临时 DataFrame)
    df = _navs_to_dataframe(navs_sorted)
    data = FundNavData(dataname=df)
    cerebro.adddata(data)

    # 策略
    strategy_info = STRATEGY_REGISTRY[strategy_name]
    params = {**strategy_info["default_params"]}
    if strategy_params:
        params.update(strategy_params)
    logger.info(f"  策略参数: {params}")
    cerebro.addstrategy(strategy_info["cls"], **params)

    # Analyzers
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return', timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, riskfreerate=0.0, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

    # ---- 跑回测 ----
    results = cerebro.run()
    strat = results[0]
    final_value = cerebro.broker.getvalue()

    # ---- 提取 analyzer 结果 ----
    sharpe_analysis = strat.analyzers.sharpe.get_analysis()
    drawdown_analysis = strat.analyzers.drawdown.get_analysis()
    trades_analysis = strat.analyzers.trades.get_analysis()
    time_return_analysis = strat.analyzers.time_return.get_analysis()
    sqn_analysis = strat.analyzers.sqn.get_analysis()

    # ---- 买入持有基准 (对所有策略都做) ----
    bh_equity, bh_total_return = _buy_and_hold_benchmark(navs_sorted, initial_capital, commission_pct)

    # ---- 构建策略 equity curve ----
    strategy_equity = []
    cum_value = initial_capital
    for date_key, daily_return in time_return_analysis.items():
        # time_return 的键可能是 datetime, 也可能是 float (ordinal)
        if isinstance(date_key, (int, float)):
            dt_str = bt.num2date(date_key).strftime("%Y-%m-%d")
        elif isinstance(date_key, datetime):
            dt_str = date_key.strftime("%Y-%m-%d")
        else:
            dt_str = str(date_key)[:10]  # 兜底
        cum_value *= (1 + daily_return)
        # 对应的买入持有值
        bh_value_at_date = bh_equity.get(dt_str, cum_value)
        strategy_equity.append({
            "date": dt_str,
            "value": round(cum_value, 2),
            "benchmark_value": round(bh_value_at_date, 2),
        })

    # ---- 汇总指标 ----
    total_return_pct = (final_value - initial_capital) / initial_capital * 100
    days = (datetime.strptime(end_date, "%Y-%m-%d") -
            datetime.strptime(start_date, "%Y-%m-%d")).days
    years = max(days / 365.25, 0.25)
    annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100

    # Sharpe: backtrader 返回 None 当 std=0, 用 0
    sharpe_ratio = sharpe_analysis.get("sharperatio") or 0.0

    # DrawDown
    max_dd = drawdown_analysis.get("max", {}).get("drawdown", 0.0)
    max_dd_len = drawdown_analysis.get("max", {}).get("len", 0)

    # Trade stats
    total_trades = trades_analysis.get("total", {}).get("total", 0)
    closed_trades = trades_analysis.get("closed", {}).get("total", 0)
    won_trades = trades_analysis.get("won", {}).get("total", 0)
    lost_trades = trades_analysis.get("lost", {}).get("total", 0)
    win_rate = (won_trades / closed_trades * 100) if closed_trades > 0 else 0.0

    # SQN (System Quality Number) — Van Tharp
    sqn = sqn_analysis.get("sqn") or 0.0

    result = {
        "code": code,
        "name": name,
        "strategy": strategy_name,
        "strategy_name": strategy_info["name"],
        "strategy_params": params,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized_return, 2),
        "buy_and_hold_return_pct": round(bh_total_return, 2),
        "alpha": round(total_return_pct - bh_total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_days": max_dd_len,
        "sharpe_ratio": round(sharpe_ratio, 3),
        "sqn": round(sqn, 3),
        "total_trades": total_trades,
        "closed_trades": closed_trades,
        "winning_trades": won_trades,
        "losing_trades": lost_trades,
        "win_rate_pct": round(win_rate, 1),
        "trades": strat.trade_list,
        "equity_curve": strategy_equity,
    }

    logger.info(
        f"  ✓ 回测完成: {code} {strategy_name} "
        f"return={result['total_return_pct']:+.2f}% "
        f"sharpe={result['sharpe_ratio']:.2f} "
        f"maxdd={result['max_drawdown_pct']:.2f}% "
        f"trades={result['total_trades']} win={result['win_rate_pct']:.1f}%"
    )

    return result


def _buy_and_hold_benchmark(
    navs: list[FundNav],
    initial_capital: float,
    commission_pct: float,
) -> tuple[dict[str, float], float]:
    """
    计算买入持有基准的逐日权益曲线
    Returns:
        (equity_dict, total_return_pct)
    """
    if not navs or navs[0].nav <= 0:
        return {}, 0.0

    # 首日满仓买入 (扣手续费)
    buy_nav = navs[0].nav
    shares = (initial_capital * (1 - commission_pct)) / buy_nav
    equity_dict = {}
    for nav in navs:
        # 这里不计赎回费 (持仓中)
        equity_dict[nav.date] = round(shares * nav.nav, 2)

    total_return = (navs[-1].nav / buy_nav - 1) * 100
    return equity_dict, total_return


# ===== 便捷函数: 多策略对比 =====

def run_backtest_multi(
    code: str,
    name: str,
    navs: list[FundNav],
    initial_capital: float = 100000.0,
    commission_pct: float = 0.001,
) -> dict:
    """
    同时运行所有策略, 返回对比结果
    Returns:
        {
            "code": "...",
            "name": "...",
            "strategies": [ result1, result2, result3 ]  # 三种策略的结果
        }
    """
    all_results = []
    for strategy_name in STRATEGY_REGISTRY:
        try:
            r = run_backtest(
                code=code, name=name, navs=navs,
                strategy_name=strategy_name,
                initial_capital=initial_capital,
                commission_pct=commission_pct,
            )
            all_results.append(r)
        except Exception as e:
            logger.error(f"  ✗ 策略 {strategy_name} 失败: {e}")
            all_results.append({
                "code": code, "name": name,
                "strategy": strategy_name,
                "error": str(e),
            })

    return {
        "code": code,
        "name": name,
        "strategies": all_results,
    }
