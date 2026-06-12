"""天天基金数据源 API — 替换原 Financial Datasets API."""

import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.data.models import FundInfo, FundNav, FundMetrics

# ===== 天天基金 API =====

FUND_GZ_URL = "http://fundgz.1234567.com.cn/js/{code}.js"
FUND_DETAIL_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
FUND_INFO_URL = "http://fund.eastmoney.com/js/fundcode_search.js"
FUND_RANKING_URL = "http://fund.eastmoney.com/data/rankhandler.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://fund.eastmoney.com/",
}


def _get_text(url: str, timeout: int = 15) -> Optional[str]:
    """GET 请求获取文本"""
    try:
        with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        print(f"  [API] HTTP error: {url[:60]}... -> {e}")
        return None


# ===== 净值查询 =====

def fetch_latest_nav(code: str) -> Optional[dict]:
    """获取最新净值 (实时接口)"""
    text = _get_text(FUND_GZ_URL.format(code=code))
    if not text:
        return None
    match = re.search(r'jsonpgz\((.+)\);?$', text.strip())
    if not match:
        return None
    try:
        obj = json.loads(match.group(1))
        nav = obj.get("dwjz", "")
        nav_date = obj.get("jzrq", "")
        name = obj.get("name", "")
        if nav and nav_date:
            return {"nav": float(nav), "date": nav_date, "name": name}
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def fetch_nav_history(code: str, months: int = 12) -> list[FundNav]:
    """从 pingzhongdata 获取历史净值"""
    text = _get_text(FUND_DETAIL_URL.format(code=code))
    if not text:
        return []

    navs = []

    # Data_netWorthTrend 是历史净值(单位净值)
    match = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\])\s*;', text, re.DOTALL)
    if match:
        try:
            trend = json.loads(match.group(1))
            cutoff = (datetime.now() - timedelta(days=months * 30)).timestamp()
            for item in trend:
                ts = item.get("x", 0) / 1000
                if ts < cutoff:
                    continue
                nav_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                nav_val = item.get("y")
                if nav_val is not None:
                    navs.append(FundNav(date=nav_date, nav=float(nav_val)))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # 按日期排序
    navs.sort(key=lambda x: x.date)
    return navs


# ===== 基金基本信息 =====

def fetch_fund_info(code: str) -> Optional[FundInfo]:
    """获取基金基本信息"""
    text = _get_text(FUND_DETAIL_URL.format(code=code))
    if not text:
        return None

    info = FundInfo(code=code, name="")

    # 基金名称
    m = re.search(r'var fS_name\s*=\s*"(.*?)";', text)
    if m:
        info.name = m.group(1)

    # 基金经理
    m = re.search(r'var fS_manager\s*=\s*"(.*?)";', text)
    if m:
        info.manager = m.group(1)

    # 基金公司
    m = re.search(r'var fS_company\s*=\s*"(.*?)";', text)
    if m:
        info.company = m.group(1)

    # 成立日期
    m = re.search(r'var fS_establishDate\s*=\s*"(.*?)";', text)
    if m:
        info.establish_date = m.group(1)

    # 基金类型
    m = re.search(r'var fS_gml\s*=\s*"(.*?)";', text)
    if m:
        info.type = m.group(1)

    # 基金规模
    m = re.search(r'var fS_fundScale\s*=\s*"(.*?)";', text)
    if m:
        try:
            info.fund_size = float(m.group(1).replace("亿份", "").strip())
        except ValueError:
            pass

    return info


def fetch_fund_type(code: str) -> str:
    """获取基金类型"""
    info = fetch_fund_info(code)
    return info.type if info else ""


# ===== 基金搜索 =====

def search_fund(keyword: str) -> list[dict]:
    """搜索基金"""
    text = _get_text(FUND_INFO_URL)
    if not text:
        return []

    # JS 文件格式: var r = [["000001","华夏成长混合","股票型","huaxia","HC"], ...];
    match = re.search(r'var r\s*=\s*(\[.*?\]);', text, re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    results = []
    for item in data:
        if len(item) >= 3:
            code, name, ftype = item[0], item[1], item[2]
            if keyword.lower() in code.lower() or keyword.lower() in name.lower():
                results.append({"code": code, "name": name, "type": ftype})
    return results[:20]


# ===== 基金排行/指标 =====

def fetch_fund_metrics(code: str, months: int = 12) -> Optional[FundMetrics]:
    """获取基金分析指标"""
    text = _get_text(FUND_DETAIL_URL.format(code=code))
    if not text:
        return None

    navs = fetch_nav_history(code, months=months)
    info = fetch_fund_info(code)
    latest = fetch_latest_nav(code)

    metrics = FundMetrics(code=code)

    # 最新净值
    if latest:
        metrics.latest_nav = latest["nav"]
        metrics.latest_date = latest["date"]
    elif navs:
        metrics.latest_nav = navs[-1].nav
        metrics.latest_date = navs[-1].date

    if info:
        metrics.management_fee = 0.015  # 默认1.5%, 实际可从页面解析

    # 计算收益率
    if len(navs) >= 2:
        # 1个月
        cutoff_1m = datetime.now() - timedelta(days=30)
        navs_1m = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff_1m]
        if len(navs_1m) >= 2:
            metrics.return_1m = (navs_1m[-1].nav / navs_1m[0].nav - 1) * 100

        # 3个月
        cutoff_3m = datetime.now() - timedelta(days=90)
        navs_3m = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff_3m]
        if len(navs_3m) >= 2:
            metrics.return_3m = (navs_3m[-1].nav / navs_3m[0].nav - 1) * 100

        # 6个月
        cutoff_6m = datetime.now() - timedelta(days=180)
        navs_6m = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff_6m]
        if len(navs_6m) >= 2:
            metrics.return_6m = (navs_6m[-1].nav / navs_6m[0].nav - 1) * 100

        # 1年
        if months >= 12:
            cutoff_1y = datetime.now() - timedelta(days=365)
            navs_1y = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff_1y]
            if len(navs_1y) >= 2:
                metrics.return_1y = (navs_1y[-1].nav / navs_1y[0].nav - 1) * 100

    # 最大回撤 (1年)
    if len(navs) >= 20:
        cutoff = datetime.now() - timedelta(days=365)
        navs_year = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff]
        if len(navs_year) >= 2:
            peak = navs_year[0].nav
            max_dd = 0
            for n in navs_year:
                if n.nav > peak:
                    peak = n.nav
                dd = (peak - n.nav) / peak * 100
                if dd > max_dd:
                    max_dd = dd
            metrics.max_drawdown_1y = round(max_dd, 2)

    # 波动率 (1年)
    if len(navs) >= 20:
        cutoff = datetime.now() - timedelta(days=365)
        navs_year = [n for n in navs if datetime.strptime(n.date, "%Y-%m-%d") >= cutoff]
        if len(navs_year) >= 5:
            returns = []
            for i in range(1, len(navs_year)):
                r = (navs_year[i].nav / navs_year[i - 1].nav - 1) * 100
                returns.append(r)
            import numpy as np
            metrics.volatility_1y = round(np.std(returns) * np.sqrt(252), 2)

    # 夏普比率 (简化: 假设无风险利率 2%)
    if metrics.return_1y is not None and metrics.volatility_1y and metrics.volatility_1y > 0:
        excess = metrics.return_1y - 2.0
        metrics.sharpe_ratio = round(excess / metrics.volatility_1y, 2)

    # === 持仓数据 ===
    # 十大重仓股 (优先从新 API 获取, 包含比例)
    if not metrics.top_holdings:
        # 用季报 API 替代 stockList
        holdings = fetch_fund_holdings(code)
        if holdings:
            metrics.top_holdings = holdings
            metrics.sector_allocation = _sectorize(holdings)
        else:
            holdings, sector = _parse_holdings(text)
            metrics.top_holdings = holdings
            metrics.sector_allocation = sector
    elif metrics.top_holdings and not metrics.sector_allocation:
        metrics.sector_allocation = _sectorize(metrics.top_holdings)

    # 资产配置
    m = re.search(r'var Data_assetAllocation\s*=\s*(\{[^;]+\});', text, re.DOTALL)
    if m:
        try:
            alloc = json.loads(m.group(1))
            series = alloc.get("series", [])
            categories = alloc.get("categories", [])
            aa = {}
            for s in series:
                name = s.get("name", "")
                data = s.get("data", [])
                if data and categories:
                    aa[name] = dict(zip(categories, data))
            metrics.asset_allocation = aa
        except (json.JSONDecodeError, Exception):
            pass

    # 持有人结构
    m = re.search(r'var Data_holderStructure\s*=\s*(\{[^;]+\});', text, re.DOTALL)
    if m:
        try:
            hs = json.loads(m.group(1))
            series = hs.get("series", [])
            categories = hs.get("categories", [])
            hs_dict = {}
            for s in series:
                name = s.get("name", "")
                data = s.get("data", [])
                if data and categories:
                    hs_dict[name] = dict(zip(categories, data))
            metrics.holder_structure = hs_dict
        except (json.JSONDecodeError, Exception):
            pass

    # 股票仓位 (从 Data_fundSharesPositions 获取最新)
    # 数据格式: [[ts1, p1], [ts2, p2], ...] — 嵌套数组, 贪婪匹配
    m = re.search(r'var Data_fundSharesPositions\s*=\s*(\[(?:\[[^\]]*\]\s*,?\s*)+\]);', text, re.DOTALL)
    if m:
        try:
            positions = json.loads(m.group(1))
            if positions and isinstance(positions[-1], (list, tuple)) and len(positions[-1]) >= 2:
                metrics.stock_position_ratio = float(positions[-1][1])
        except (json.JSONDecodeError, Exception):
            pass

    return metrics


def fetch_fund_holdings(code: str, year=None, month=None) -> list:
    """获取基金最新季报披露的前十大重仓股

    通过 fundf10.eastmoney.com 的 FundArchivesDatas API 获取
    包含股票代码、名称、占净值比例
    """
    from src.data.models import FundHolding
    import re
    from datetime import datetime

    if year is None or month is None:
        now = datetime.now()
        # 季报披露规则: 1/4月用去年Q3(9月), 7月用Q1(3月), 10月用Q2(6月)
        if now.month >= 4 and now.month <= 6:
            year, month = now.year, 3  # Q1 季报
        elif now.month >= 7 and now.month <= 9:
            year, month = now.year, 6  # Q2 半年报
        elif now.month >= 10 and now.month <= 12:
            year, month = now.year, 9  # Q3 季报
        else:
            year, month = now.year - 1, 9  # Q3 季报 (1-3月)

    url = f"http://fundf10.eastmoney.com/FundArchivesDatas.aspx"
    params = {
        "type": "jjcc",
        "code": code,
        "topline": "10",
        "year": str(year),
        "month": str(month),
        "rt": "0.5",
    }
    try:
        r = httpx.get(
            url, params=params,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "http://fundf10.eastmoney.com/"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        # 提取 apidata.content (使用 split 避免正则陷阱)
        # 响应格式: var apidata={ content:"...html...",arryear:[...],curyear:2026};
        parts = r.text.split('",arryear:', 1)
        if len(parts) < 2:
            return []
        content = parts[0]
        # 截掉前缀 'var apidata={ content:"'
        prefix = 'content:"'
        idx = content.rfind(prefix)
        if idx < 0:
            return []
        html_content = content[idx + len(prefix):]

        # 提取每行: <tr>...<td>序号</td><td>代码</td><td>名称</td>...<td>比例</td>...</tr>
        # A 股代码为 6 位数字, 美股/港股代码为字母
        holdings = []
        rows = re.findall(r'<tr>(.*?)</tr>', html_content, re.DOTALL)
        for row in rows:
            # 提取股票代码 (兼容 A 股 6 位数字 和 字母代码 NVDA, AAPL, 00700 等)
            # A股: <a href='...'>300750</a>
            # 美股: <a href='...'>NVDA</a>  (没有数字限制)
            # 港股: <a href='...'>00700</a>
            code_m = re.search(r"unify/r/[^']*?['\")]*\s*>\s*([A-Za-z0-9]{1,10})\s*</a>", row)
            if not code_m:
                code_m = re.search(r">([0-9]{6})<", row)
            # 提取股票名称 (从第二个 toc td 的 <a> 中)
            name_m = re.search(r"class='toc'[^>]*>.*?<a[^>]*>([^<]+)</a>", row, re.DOTALL)
            if not name_m:
                # A股老格式
                name_m = re.search(r"class='tol'>.*?>([^<]+)</a>", row, re.DOTALL)
            # 提取比例
            ratio_m = re.search(r"(\d+\.?\d*)%", row)
            if code_m and ratio_m:
                holdings.append(FundHolding(
                    code=code_m.group(1),
                    name=name_m.group(1) if name_m else "",
                    ratio=float(ratio_m.group(1)),
                ))

        # 季报回退: 找不到时尝试上一季度
        if not holdings and month > 3:
            return fetch_fund_holdings(code, year, 3)
        if not holdings and month > 6:
            return fetch_fund_holdings(code, year, 6)
        if not holdings and month > 9:
            return fetch_fund_holdings(code, year, 9)
        return holdings[:10]
    except Exception:
        return []


def _sectorize(holdings: list) -> dict:
    """根据持仓股票代码推断行业分布"""
    sector = {}
    for h in holdings:
        sec = _classify_sector(h.code)
        sector[sec] = sector.get(sec, 0) + 1
    return sector


def _parse_holdings(text: str) -> tuple[list, dict]:
    """从 pingzhongdata JS 解析持仓信息"""
    from src.data.models import FundHolding

    # 股票代码列表
    codes = []
    m = re.search(r'var stockCodes\s*=\s*(\[[^\]]+\]);', text)
    if m:
        try:
            codes = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试解析持仓比例 (从 equity portfolio 或同类接口)
    # 东方财富新版本使用 stockList 变量
    holdings = []
    m = re.search(r'var stockList\s*=\s*(\[[^\]]+\]);', text, re.DOTALL)
    if m:
        try:
            stock_list = json.loads(m.group(1))
            for item in stock_list:
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    holdings.append(FundHolding(
                        code=str(item[0]),
                        name=str(item[1]),
                        ratio=float(item[2]) if item[2] else 0.0,
                    ))
        except (json.JSONDecodeError, ValueError):
            pass

    # 如果 stockList 不可用，用股票代码占位（无比例）
    if not holdings and codes:
        for c in codes[:10]:
            # 去掉市场号后缀，取纯代码部分
            code = re.sub(r'\.\d+$|105$|106$', '', str(c))
            holdings.append(FundHolding(code=code, name="", ratio=0.0))

    # 行业分布 (解析股票代码前缀判断行业 — 简化版)
    sector = {}
    for h in holdings:
        sec = _classify_sector(h.code)
        sector[sec] = sector.get(sec, 0) + 1

    return holdings, sector


def _classify_sector(code: str) -> str:
    """简单行业分类 — 涵盖 A 股/港股/美股"""
    if not code:
        return "其他"
    code_str = str(code).strip()
    code_upper = code_str.upper()

    # === 美股科技 ===
    if any(t in code_upper for t in ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "NVDA", "AVGO", "AMD", "INTC", "CRM", "ORCL", "ADBE", "NOW", "IBM", "CSCO", "QCOM", "TXN"]):
        return "科技"

    # === 美股互联网 ===
    if any(t in code_upper for t in ["AMZN", "NFLX", "SNAP", "PINS", "SPOT", "UBER", "LYFT"]):
        return "互联网"

    # === 港股科技/互联网 ===
    if code_str.startswith("0") and len(code_str) == 5:
        if code_str in ["00700", "03690"]:  # 腾讯, 美团
            return "互联网"
        if code_str in ["00981", "00992", "01024", "09618", "09688", "09988", "09999", "01088", "01810", "02318", "02333", "00388"]:
            return "互联网/科技"

    # === A 股行业（按代码前缀规律分类） ===
    # 沪市主板: 60xxxx, 科创板: 688xxx
    # 深市主板: 000xxx, 中小板: 002xxx, 创业板: 300xxx
    if code_str.isdigit() and len(code_str) == 6:
        # 科创板
        if code_str.startswith("688"):
            return "科技/科创"
        # 创业板 (科技/医药/新能源居多)
        if code_str.startswith("300"):
            return "科技/成长"
        # 沪深300主要成分股 - 按已知代码分类
        cn_known = {
            # 银行
            "601398": "金融-银行", "601939": "金融-银行", "601288": "金融-银行", "601988": "金融-银行",
            "600036": "金融-银行", "600000": "金融-银行", "600016": "金融-银行", "601166": "金融-银行",
            "600030": "金融-证券", "601688": "金融-证券", "601995": "金融-证券", "600837": "金融-证券",
            "601318": "金融-保险", "601628": "金融-保险", "601336": "金融-保险",
            # 白酒
            "600519": "消费-白酒", "000858": "消费-白酒", "000568": "消费-白酒", "600809": "消费-白酒",
            "002304": "消费-白酒", "000596": "消费-白酒", "603369": "消费-白酒",
            # 食品
            "000895": "消费-食品", "603288": "消费-食品", "600887": "消费-食品",
            # 家电
            "000333": "消费-家电", "000651": "消费-家电", "000418": "消费-家电", "600690": "消费-家电",
            # 汽车
            "002594": "消费-汽车", "601633": "消费-汽车", "600104": "消费-汽车", "601238": "消费-汽车",
            "601127": "消费-汽车", "000625": "消费-汽车", "002460": "消费-新能源",
            # 医药
            "600276": "医药", "000538": "医药", "600436": "医药", "000661": "医药", "300760": "医药",
            "600196": "医药", "002007": "医药", "300015": "医药", "600085": "医药",
            # 科技
            "300750": "科技-新能源", "002475": "科技-消费电子", "300059": "科技-金融",
            "600588": "科技-软件", "300033": "科技-软件", "000063": "科技-通信",
            "002415": "科技-安防", "002230": "科技-AI", "300033": "科技",
            "300308": "科技-通信", "002466": "科技-锂电", "002460": "科技-锂电",
            "300274": "科技-光伏", "601012": "科技-光伏", "002129": "科技-光伏",
            "300124": "科技-工控", "300014": "科技-锂电",
            # 资源
            "601899": "资源-有色", "601088": "资源-煤炭", "601225": "资源-煤炭",
            "600028": "资源-石化", "601857": "资源-石化", "600938": "资源-石油",
            "601628": "金融-保险",  # 重复可以
            "600050": "通信", "600941": "通信", "601728": "通信",
            # 基建/工业
            "601668": "工业-建筑", "601800": "工业-建筑", "601390": "工业-建筑",
            "600585": "工业-建材", "600031": "工业-机械", "601100": "工业-机械",
            # 地产
            "000002": "地产", "600048": "地产", "001979": "地产", "600340": "地产",
        }
        if code_str in cn_known:
            return cn_known[code_str]

        # 通用分类
        if code_str.startswith(("002", "003")):
            return "中小盘"
        if code_str.startswith(("300", "301")):
            return "成长/创业板"
        if code_str.startswith(("600", "601", "603", "605")):
            return "沪市主板"
        if code_str.startswith("000") or code_str.startswith("001"):
            return "深市主板"

    # === 美股中概 ===
    if any(t in code_upper for t in ["BABA", "TENCENT", "MEITUAN", "PDD", "JD", "BIDU", "NIO", "LI", "XPEV", "BILI", "TME", "NTES", "YUMC"]):
        return "中概股"

    # === 美股消费/医药/金融/能源/工业 ===
    if any(t in code_upper for t in ["TSLA", "PG", "KO", "PEP", "WMT", "COST", "MCD", "SBUX", "DIS", "NKE", "LVMUY", "HD", "LOW", "TGT", "BKNG"]):
        return "消费"
    if any(t in code_upper for t in ["JNJ", "PFE", "UNH", "ABBV", "MRK", "ABT", "LLY", "TMO", "DHR", "BMY", "AMGN", "GILD", "MERCK", "MDT"]):
        return "医药"
    if any(t in code_upper for t in ["BRK_B", "BRK.A", "JPM", "BAC", "GS", "MS", "V", "MA", "WFC", "C", "AXP", "BLK", "SCHW"]):
        return "金融"
    if any(t in code_upper for t in ["XOM", "CVX", "COP", "EOG", "SLB", "BP", "SHEL", "TTE", "OXY"]):
        return "能源"
    if any(t in code_upper for t in ["CAT", "GE", "HON", "BA", "MMM", "UPS", "UNP", "RTX", "LMT", "DE", "NOC"]):
        return "工业"

    return "其他"
