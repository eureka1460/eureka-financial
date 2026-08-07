"""
财务数据相关 Pydantic 请求/响应模型。
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


# ── 财务报表记录 ──────────────────────────────────────────
class FinancialRecord(BaseModel):
    """一条完整的财务报表记录（含原始数据 + 计算指标）。"""

    # 元数据
    report_date: Optional[date] = None
    report_type: Optional[str] = None
    fiscal_year: Optional[int] = None

    # 资产负债表 — 核心
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    fixed_assets: Optional[float] = None
    goodwill: Optional[float] = None
    intangible_assets: Optional[float] = None
    short_term_borrowings: Optional[float] = None
    long_term_borrowings: Optional[float] = None

    # 利润表 — 核心
    operating_revenue: Optional[float] = None
    operating_cost: Optional[float] = None
    operating_profit: Optional[float] = None
    total_profit: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_attr_parent: Optional[float] = None
    net_profit_excl_nonrecurring: Optional[float] = None
    basic_eps: Optional[float] = None
    r_and_d_expenses: Optional[float] = None
    selling_expenses: Optional[float] = None
    administrative_expenses: Optional[float] = None
    financial_expenses: Optional[float] = None

    # 现金流量表 — 核心
    net_operating_cashflow: Optional[float] = None
    net_investing_cashflow: Optional[float] = None
    net_financing_cashflow: Optional[float] = None
    capital_expenditure: Optional[float] = None
    ending_cash_balance: Optional[float] = None

    # 计算指标 — 核心
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
    debt_to_equity: Optional[float] = None
    fcf: Optional[float] = None
    book_value_per_share: Optional[float] = None

    model_config = {"from_attributes": True}


# ── 可筛选指标元数据 ──────────────────────────────────────
class IndicatorMeta(BaseModel):
    """单个可筛选指标的元数据（供前端构建筛选 UI）。"""

    field: str = Field(..., description="字段名")
    chinese_name: str = Field(..., description="中文名称")
    unit: str = Field(..., description="单位（元/%/倍）")
    category: str = Field(..., description="分类标签")
    is_ratio: bool = Field(False, description="是否为比率型指标")


# ── 数据同步请求 ──────────────────────────────────────────
class SyncRequest(BaseModel):
    """触发 ETL 数据同步的请求体。"""

    sync_type: str = Field("full_sync", description="同步类型: full_sync / incremental_sync / batch_sync")
    years: int = Field(5, ge=1, le=10, description="抓取年数")
    symbols: Optional[list[str]] = Field(None, max_items=100, description="指定股票代码列表")
    report_types: Optional[list[str]] = Field(None, description="指定报表类型")
    batch_size: Optional[int] = Field(None, ge=10, le=200, description="分批大小(batch_sync时使用)")
    start_from: Optional[int] = Field(None, ge=0, description="起始位置(断点续传)")
