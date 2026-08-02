"""
股票相关 Pydantic 请求/响应模型。
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── 股票列表项 ────────────────────────────────────────────
class StockSummary(BaseModel):
    """股票列表中的每一项（精简信息）。"""

    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票简称")
    market: str = Field(..., description="交易所: SH/SZ/BJ")
    industry: Optional[str] = Field(None, description="申万一级行业")
    list_date: Optional[date] = Field(None, description="上市日期")
    total_shares: Optional[float] = Field(None, description="总股本")

    model_config = {"from_attributes": True}


# ── 最新财务摘要 ──────────────────────────────────────────
class LatestFinancialSummary(BaseModel):
    """股票详情中嵌套的最新财务指标摘要。"""

    report_date: Optional[date] = None
    report_type: Optional[str] = None
    fiscal_year: Optional[int] = None
    operating_revenue: Optional[float] = None
    net_profit_attr_parent: Optional[float] = None
    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    basic_eps: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    revenue_yoy: Optional[float] = None
    net_profit_yoy: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None
    fcf: Optional[float] = None
    book_value_per_share: Optional[float] = None

    model_config = {"from_attributes": True}


# ── 股票详情 ──────────────────────────────────────────────
class StockDetail(BaseModel):
    """单只股票完整信息 + 最新财务摘要。"""

    symbol: str
    name: str
    market: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    list_date: Optional[date] = None
    is_active: bool = True
    total_shares: Optional[float] = None
    latest_financial: Optional[LatestFinancialSummary] = None

    model_config = {"from_attributes": True}
