"""LangGraph 状态定义 — AI 基金分析"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.data.models import FundSignal, FundInfo, FundMetrics, FundNav


class FundData(BaseModel):
    """单只基金的完整数据"""
    code: str
    name: str = ""
    info: Optional[FundInfo] = None
    metrics: Optional[FundMetrics] = None
    navs: list[FundNav] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""


class AgentState(BaseModel):
    """LangGraph 状态 — 每个 Agent 使用独立字段避免并行写入冲突"""

    # 当前正在分析的基金
    current_fund: Optional[FundData] = None

    # 所有基金的分析结果
    fund_results: dict[str, Any] = Field(default_factory=dict)

    # 各 Agent 独立字段 (避免并行写入冲突)
    signal_trend: Optional[dict] = None
    signal_risk: Optional[dict] = None
    signal_manager: Optional[dict] = None
    signal_valuation: Optional[dict] = None
    signal_peer: Optional[dict] = None
    signal_llm: Optional[dict] = None
    signal_holdings: Optional[dict] = None

    # 已完成分析的基金代码列表
    completed_codes: list[str] = Field(default_factory=list)

    # 配置
    show_reasoning: bool = False
    use_llm: bool = False

    # 工作流状态
    remaining_codes: list[str] = Field(default_factory=list)
    current_code: str = ""
