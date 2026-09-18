"""
财务数据查询 API 路由。

提供财务历史查询和可筛选指标列表。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import StockNotFoundException
from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator
from app.schemas.common import APIResponse
from app.schemas.financials import FinancialRecord, IndicatorMeta

router = APIRouter(prefix="/api/v1", tags=["financials"])


def _f(val):
    """安全转换 Decimal → float。"""
    return float(val) if val is not None else None


# ═══════════════════════════════════════════════════════════════
# 财务历史
# ═══════════════════════════════════════════════════════════════
@router.get(
    "/stocks/{symbol}/financials",
    response_model=APIResponse[list[FinancialRecord]],
)
def get_financials(
    symbol: str,
    report_type: Optional[str] = Query(
        None, description="筛选报表类型: annual/semi_annual/q1/q3"
    ),
    years: int = Query(5, ge=1, le=20, description="返回最近 N 年数据"),
    db: Session = Depends(get_db),
):
    """获取单只股票的完整财务历史。

    返回 financial_statements + financial_indicators 的联合数据，
    按 report_date 降序排列。
    """
    # 验证股票存在
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise StockNotFoundException(symbol)

    # 基础查询
    query = (
        db.query(FinancialStatement)
        .filter(FinancialStatement.symbol == symbol)
    )

    # 报表类型筛选
    if report_type:
        query = query.filter(FinancialStatement.report_type == report_type)

    # 年限筛选：包含当前年度在内的最近 N 个自然年度
    from datetime import datetime as dt
    current_year = dt.now().year
    min_year = current_year - years + 1
    query = query.filter(
        FinancialStatement.fiscal_year >= min_year
    )

    stmts = query.order_by(FinancialStatement.report_date.desc()).all()

    # 批量获取对应的指标
    indicator_map = {}
    if stmts:
        ind_query = db.query(FinancialIndicator).filter(
            FinancialIndicator.symbol == symbol,
            FinancialIndicator.fiscal_year >= min_year,
        )
        if report_type:
            ind_query = ind_query.filter(FinancialIndicator.report_type == report_type)
        for ind in ind_query.all():
            indicator_map[(ind.symbol, ind.report_date, ind.report_type)] = ind

    # 组装响应
    records = []
    for s in stmts:
        ind = indicator_map.get((s.symbol, s.report_date, s.report_type))
        records.append(_build_financial_record(s, ind))

    return APIResponse(data=records)


def _build_financial_record(stmt, ind) -> FinancialRecord:
    """将 ORM 对象转换为 FinancialRecord Pydantic 模型。"""
    return FinancialRecord(
        # 元数据
        report_date=stmt.report_date,
        report_type=stmt.report_type,
        fiscal_year=stmt.fiscal_year,
        # 资产负债表
        total_assets=_f(stmt.total_assets),
        total_liabilities=_f(stmt.total_liabilities),
        total_equity=_f(stmt.total_equity),
        current_assets=_f(stmt.current_assets),
        current_liabilities=_f(stmt.current_liabilities),
        cash_and_equivalents=_f(stmt.cash_and_equivalents),
        accounts_receivable=_f(stmt.accounts_receivable),
        inventory=_f(stmt.inventory),
        fixed_assets=_f(stmt.fixed_assets),
        goodwill=_f(stmt.goodwill),
        intangible_assets=_f(stmt.intangible_assets),
        short_term_borrowings=_f(stmt.short_term_borrowings),
        long_term_borrowings=_f(stmt.long_term_borrowings),
        # 利润表
        operating_revenue=_f(stmt.operating_revenue),
        operating_cost=_f(stmt.operating_cost),
        operating_profit=_f(stmt.operating_profit),
        total_profit=_f(stmt.total_profit),
        net_profit=_f(stmt.net_profit),
        net_profit_attr_parent=_f(stmt.net_profit_attr_parent),
        net_profit_excl_nonrecurring=_f(stmt.net_profit_excl_nonrecurring),
        basic_eps=_f(stmt.basic_eps),
        r_and_d_expenses=_f(stmt.r_and_d_expenses),
        selling_expenses=_f(stmt.selling_expenses),
        administrative_expenses=_f(stmt.administrative_expenses),
        financial_expenses=_f(stmt.financial_expenses),
        # 现金流量表
        net_operating_cashflow=_f(stmt.net_operating_cashflow),
        net_investing_cashflow=_f(stmt.net_investing_cashflow),
        net_financing_cashflow=_f(stmt.net_financing_cashflow),
        capital_expenditure=_f(stmt.capital_expenditure),
        ending_cash_balance=_f(stmt.ending_cash_balance),
        # 计算指标
        roe=_f(ind.roe) if ind else None,
        roa=_f(ind.roa) if ind else None,
        gross_margin=_f(ind.gross_margin) if ind else None,
        net_margin=_f(ind.net_margin) if ind else None,
        operating_margin=_f(ind.operating_margin) if ind else None,
        revenue_yoy=_f(ind.revenue_yoy) if ind else None,
        net_profit_yoy=_f(ind.net_profit_yoy) if ind else None,
        current_ratio=_f(ind.current_ratio) if ind else None,
        quick_ratio=_f(ind.quick_ratio) if ind else None,
        debt_to_assets=_f(ind.debt_to_assets) if ind else None,
        debt_to_equity=_f(ind.debt_to_equity) if ind else None,
        fcf=_f(ind.fcf) if ind else None,
        book_value_per_share=_f(ind.book_value_per_share) if ind else None,
    )


# ═══════════════════════════════════════════════════════════════
# 可筛选指标列表
# ═══════════════════════════════════════════════════════════════
@router.get("/indicators", response_model=APIResponse[list[IndicatorMeta]])
def list_indicators():
    """返回所有可用于筛选的财务指标元数据。

    前端用这个接口构建筛选条件 UI，
    包含每个指标的中文名、单位、分类等信息。
    """
    indicators = [
        # 盈利能力
        IndicatorMeta(field="roe", chinese_name="净资产收益率(ROE)", unit="%", category="盈利能力", is_ratio=True),
        IndicatorMeta(field="roa", chinese_name="总资产收益率(ROA)", unit="%", category="盈利能力", is_ratio=True),
        IndicatorMeta(field="gross_margin", chinese_name="毛利率", unit="%", category="盈利能力", is_ratio=True),
        IndicatorMeta(field="net_margin", chinese_name="净利率", unit="%", category="盈利能力", is_ratio=True),
        IndicatorMeta(field="operating_margin", chinese_name="营业利润率", unit="%", category="盈利能力", is_ratio=True),
        # 成长能力
        IndicatorMeta(field="revenue_yoy", chinese_name="营收同比增长率", unit="%", category="成长能力", is_ratio=True),
        IndicatorMeta(field="net_profit_yoy", chinese_name="归母净利润同比增长率", unit="%", category="成长能力", is_ratio=True),
        IndicatorMeta(field="operating_profit_yoy", chinese_name="营业利润同比增长率", unit="%", category="成长能力", is_ratio=True),
        IndicatorMeta(field="eps_yoy", chinese_name="EPS同比增长率", unit="%", category="成长能力", is_ratio=True),
        # 偿债与流动性
        IndicatorMeta(field="current_ratio", chinese_name="流动比率", unit="倍", category="偿债能力", is_ratio=True),
        IndicatorMeta(field="quick_ratio", chinese_name="速动比率", unit="倍", category="偿债能力", is_ratio=True),
        IndicatorMeta(field="debt_to_assets", chinese_name="资产负债率", unit="%", category="偿债能力", is_ratio=True),
        IndicatorMeta(field="debt_to_equity", chinese_name="权益乘数", unit="倍", category="偿债能力", is_ratio=True),
        IndicatorMeta(field="interest_coverage", chinese_name="利息保障倍数", unit="倍", category="偿债能力", is_ratio=True),
        # 营运效率
        IndicatorMeta(field="asset_turnover", chinese_name="总资产周转率", unit="倍", category="营运效率", is_ratio=True),
        # 估值相关
        IndicatorMeta(field="fcf", chinese_name="自由现金流(FCF)", unit="元", category="估值相关", is_ratio=False),
        IndicatorMeta(field="book_value_per_share", chinese_name="每股净资产", unit="元", category="估值相关", is_ratio=False),
        # 财务报表原始字段
        IndicatorMeta(field="operating_revenue", chinese_name="营业总收入", unit="元", category="利润表", is_ratio=False),
        IndicatorMeta(field="operating_profit", chinese_name="营业利润", unit="元", category="利润表", is_ratio=False),
        IndicatorMeta(field="net_profit_attr_parent", chinese_name="归母净利润", unit="元", category="利润表", is_ratio=False),
        IndicatorMeta(field="total_assets", chinese_name="总资产", unit="元", category="资产负债表", is_ratio=False),
        IndicatorMeta(field="total_equity", chinese_name="净资产", unit="元", category="资产负债表", is_ratio=False),
        IndicatorMeta(field="net_operating_cashflow", chinese_name="经营现金流", unit="元", category="现金流量表", is_ratio=False),
        IndicatorMeta(field="basic_eps", chinese_name="基本每股收益(EPS)", unit="元", category="利润表", is_ratio=False),
        IndicatorMeta(field="r_and_d_expenses", chinese_name="研发费用", unit="元", category="利润表", is_ratio=False),
    ]

    return APIResponse(data=indicators)
