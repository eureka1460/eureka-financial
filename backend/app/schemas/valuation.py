"""
估值相关 Pydantic 请求/响应模型。
"""

from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# DCF
# ═══════════════════════════════════════════════════════════════
class DCFRequest(BaseModel):
    """DCF 估值请求。

    任何参数传 null 则自动从数据库填充。
    """

    symbol: str = Field(..., description="股票代码")
    fcf_base: Optional[float] = Field(
        None, description="基期自由现金流（null=自动填充）"
    )
    forecast_years: int = Field(
        5, ge=1, le=20, description="可明确预测年数"
    )
    growth_rate_stage1: float = Field(
        0.10, ge=-1.0, le=10.0, description="阶段一增长率"
    )
    growth_rate_terminal: float = Field(
        0.03, ge=-1.0, le=1.0, description="永续增长率"
    )
    wacc: float = Field(
        0.08, ge=0.001, le=1.0, description="加权平均资本成本"
    )
    net_debt: Optional[float] = Field(
        None, description="净负债（null=自动填充）"
    )
    total_shares: Optional[float] = Field(
        None, description="总股本（null=自动填充）"
    )


class DCFResult(BaseModel):
    """DCF 估值结果。"""

    enterprise_value: float = Field(..., description="企业价值")
    equity_value: float = Field(..., description="股权价值")
    fair_value_per_share: float = Field(..., description="每股内在价值")
    pv_stage1: float = Field(..., description="阶段一现值")
    pv_terminal: float = Field(..., description="终值现值")


class DCFResponse(BaseModel):
    """DCF 估值完整响应（含输入参数 + 计算结果）。"""

    input_params: dict = Field(..., description="使用的参数及其来源")
    result: DCFResult


# ═══════════════════════════════════════════════════════════════
# DDM
# ═══════════════════════════════════════════════════════════════
class DDMRequest(BaseModel):
    """DDM 估值请求。"""

    symbol: str = Field(..., description="股票代码")
    d0: Optional[float] = Field(
        None, description="基期每股股利（null=自动填充）"
    )
    forecast_years: int = Field(
        5, ge=1, le=20, description="可明确预测年数"
    )
    growth_rate_stage1: float = Field(
        0.08, ge=-1.0, le=10.0, description="阶段一增长率"
    )
    growth_rate_terminal: float = Field(
        0.02, ge=-1.0, le=1.0, description="永续增长率"
    )
    required_return: float = Field(
        0.07, ge=0.001, le=1.0, description="要求回报率"
    )


class DDMResult(BaseModel):
    """DDM 估值结果。"""

    fair_value_per_share: float = Field(..., description="每股内在价值")
    pv_stage1: float = Field(..., description="阶段一现值")
    pv_terminal: float = Field(..., description="终值现值")


class DDMResponse(BaseModel):
    """DDM 估值完整响应。"""

    input_params: dict = Field(..., description="使用的参数及其来源")
    result: DDMResult
