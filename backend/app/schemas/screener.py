"""
筛选相关 Pydantic 请求/响应模型。
"""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class MetricExpression(BaseModel):
    """指标间运算表达式。

    当 metric 为简单字段名时，expression 为 None。
    当需要指标间运算时，expression 为算术表达式字符串。
    例："(net_operating_cashflow - capital_expenditure) / net_profit_attr_parent"
    """

    expression: str = Field(..., description="包含指标字段名的算术表达式")


class FilterCondition(BaseModel):
    """单条筛选条件。"""

    metric: Optional[str] = Field(
        None,
        description="简单指标字段名（与 expression 二选一）",
    )
    expression: Optional[str] = Field(
        None,
        description="指标运算表达式（与 metric 二选一）",
    )
    operator: str = Field(
        ">=",
        description="比较运算符: > / >= / < / <= / == / !=",
    )
    value: float = Field(
        ...,
        description="比较阈值",
    )
    consecutive_years: int = Field(
        1,
        ge=1,
        le=10,
        description="连续满足的年数（默认1，即仅最近一年）",
    )

    @model_validator(mode="after")
    def check_metric_or_expression(self):
        if not self.metric and not self.expression:
            raise ValueError("必须提供 metric 或 expression 之一")
        return self


class ScreenerRequest(BaseModel):
    """选股筛选请求。"""

    conditions: list[FilterCondition] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="筛选条件列表（至少1个）",
    )
    logic: str = Field(
        "AND",
        description="条件组合逻辑: AND / OR",
    )
    report_type: str = Field(
        "annual",
        description="适用的报表类型: annual / q1 / semi_annual / q3",
    )
    industry_filter: Optional[list[str]] = Field(
        None,
        description="行业筛选列表（申万一级行业名）",
    )
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class MatchDetail(BaseModel):
    """单只股票的筛选匹配详情。"""

    latest_values: dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="各项指标的最新值",
    )
    conditions_passed: int = Field(..., description="满足的条件数")
    conditions_total: int = Field(..., description="总条件数")


class ScreenerResultItem(BaseModel):
    """筛选结果中的每一项。"""

    symbol: str
    name: str
    industry: Optional[str] = None
    match_detail: MatchDetail
