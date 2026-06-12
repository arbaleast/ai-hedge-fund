"""Fund analysis data models — replaces the original stock models."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ===== 基金净值数据 =====

class FundNav(BaseModel):
    """单日基金净值"""
    date: str
    nav: float  # 单位净值
    acc_nav: Optional[float] = None  # 累计净值
    daily_return: Optional[float] = None  # 日收益率 (%)


class FundNavResponse(BaseModel):
    """基金净值序列"""
    code: str
    name: str
    navs: list[FundNav]


# ===== 基金基本信息 =====

class FundInfo(BaseModel):
    """基金基本信息"""
    code: str
    name: str
    type: str = ""  # 股票型, 混合型, 债券型, 指数型, QDII
    manager: str = ""
    manager_start: str = ""  # 经理任职起始日期
    fund_size: float = 0  # 基金规模(亿)
    establish_date: str = ""  # 成立日期
    company: str = ""  # 基金公司


# ===== 基金分析指标 =====

class FundHolding(BaseModel):
    """基金持仓股票"""
    code: str = ""
    name: str = ""
    ratio: float = 0.0  # 占净值比例%


class FundMetrics(BaseModel):
    """基金分析指标"""
    code: str
    
    # 收益指标
    latest_nav: float = 0
    latest_date: str = ""
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None
    return_ytd: Optional[float] = None
    
    # 风险指标
    max_drawdown_1y: Optional[float] = None
    max_drawdown_3y: Optional[float] = None
    volatility_1y: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    
    # 排名
    ranking_1y: Optional[str] = None  # e.g., "23/185"
    ranking_3y: Optional[str] = None
    
    # 持仓
    top_holdings: list[FundHolding] = Field(default_factory=list)  # 十大重仓股
    sector_allocation: dict = Field(default_factory=dict)  # 行业分布
    stock_position_ratio: Optional[float] = None  # 股票仓位%
    asset_allocation: dict = Field(default_factory=dict)  # 资产配置(股票/债券/现金%)
    holder_structure: dict = Field(default_factory=dict)  # 持有人结构(机构/个人%)
    
    # 费率
    management_fee: Optional[float] = None  # 管理费%
    custodian_fee: Optional[float] = None  # 托管费%


# ===== QDII 特定分析 =====

class QdiiAnalysis(BaseModel):
    """QDII 基金跨市场分析"""
    code: str
    asset_name: str  # 跟踪标的名称
    tracking_error: Optional[float] = None  # 跟踪误差
    fx_impact: Optional[float] = None  # 汇率影响
    peer_rank: Optional[str] = None  # 同类排名
    fee_analysis: dict = Field(default_factory=dict)  # 费率对比


# ===== Agent 信号 =====

class FundSignal(BaseModel):
    """Agent 输出的基金分析信号"""
    signal: str = "neutral"  # bullish / neutral / bearish
    confidence: float = 0.0  # 0-100
    reasoning: dict | str | None = None
    score: float = 0.0  # 综合评分 0-100


class FundAnalysis(BaseModel):
    """单只基金的完整分析"""
    code: str
    name: str = ""
    final_signal: str = "neutral"
    score: float = 0.0
    confidence: int = 0
    agent_signals: dict[str, FundSignal] = Field(default_factory=dict)
    summary: dict[str, dict] = Field(default_factory=dict)


# ===== Graph State =====

class AgentStateData(BaseModel):
    """Graph 共享数据"""
    fund_codes: list[str]
    start_date: str
    end_date: str
    fund_analyses: dict[str, FundAnalysis] = Field(default_factory=dict)
    agent_signals: dict[str, dict] = Field(default_factory=dict)


class AgentStateMetadata(BaseModel):
    """Graph 元数据"""
    show_reasoning: bool = False
    model_name: str = "deepseek-chat"
    model_provider: str = "OpenAI"
