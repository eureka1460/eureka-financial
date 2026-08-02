"""
股票查询 API 路由。

提供股票列表搜索、单只股票详情查询。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.exceptions import StockNotFoundException
from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator
from app.schemas.common import APIResponse, PaginatedData, PaginationParams
from app.schemas.stocks import StockSummary, StockDetail, LatestFinancialSummary

router = APIRouter(prefix="/api/v1", tags=["stocks"])


# ═══════════════════════════════════════════════════════════════
# 股票列表
# ═══════════════════════════════════════════════════════════════
@router.get("/stocks", response_model=APIResponse[PaginatedData[StockSummary]])
def list_stocks(
    keyword: Optional[str] = Query(None, description="按股票代码或名称搜索"),
    industry: Optional[str] = Query(None, description="按申万一级行业筛选"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """分页获取股票列表，支持关键词搜索和行业筛选。"""
    query = db.query(Stock)

    # 关键词搜索：匹配代码或名称
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(Stock.symbol.like(kw), Stock.name.like(kw))
        )

    # 行业筛选
    if industry:
        query = query.filter(Stock.industry == industry)

    total = query.count()
    stocks = (
        query.order_by(Stock.symbol)
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .all()
    )

    items = [StockSummary.model_validate(s) for s in stocks]

    return APIResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    )


# ═══════════════════════════════════════════════════════════════
# 股票详情
# ═══════════════════════════════════════════════════════════════
@router.get("/stocks/{symbol}", response_model=APIResponse[StockDetail])
def get_stock_detail(
    symbol: str,
    db: Session = Depends(get_db),
):
    """获取单只股票基本信息 + 最新财务指标摘要。"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise StockNotFoundException(symbol)

    # 查询最新一条年报指标（年报才有完整的 YoY/ROA 等指标）
    latest_indicator = (
        db.query(FinancialIndicator)
        .filter(FinancialIndicator.symbol == symbol, FinancialIndicator.report_type == "annual")
        .order_by(FinancialIndicator.report_date.desc())
        .first()
    )
    # 如果没年报指标，降级取最新任意报表的指标
    if not latest_indicator:
        latest_indicator = (
            db.query(FinancialIndicator)
            .filter(FinancialIndicator.symbol == symbol)
            .order_by(FinancialIndicator.report_date.desc())
            .first()
        )

    # 查询最新一条原始财报
    latest_stmt = (
        db.query(FinancialStatement)
        .filter(FinancialStatement.symbol == symbol)
        .order_by(FinancialStatement.report_date.desc())
        .first()
    )

    # 组装财务摘要
    summary = None
    if latest_stmt:
        summary = LatestFinancialSummary(
            report_date=latest_stmt.report_date,
            report_type=latest_stmt.report_type,
            fiscal_year=latest_stmt.fiscal_year,
            operating_revenue=_f(latest_stmt.operating_revenue),
            net_profit_attr_parent=_f(latest_stmt.net_profit_attr_parent),
            total_assets=_f(latest_stmt.total_assets),
            total_equity=_f(latest_stmt.total_equity),
            basic_eps=_f(latest_stmt.basic_eps),
            roe=_f(latest_indicator.roe) if latest_indicator else None,
            gross_margin=_f(latest_indicator.gross_margin) if latest_indicator else None,
            net_margin=_f(latest_indicator.net_margin) if latest_indicator else None,
            revenue_yoy=_f(latest_indicator.revenue_yoy) if latest_indicator else None,
            net_profit_yoy=_f(latest_indicator.net_profit_yoy) if latest_indicator else None,
            debt_to_assets=_f(latest_indicator.debt_to_assets) if latest_indicator else None,
            fcf=_f(latest_indicator.fcf) if latest_indicator else None,
        )

    detail = StockDetail(
        symbol=stock.symbol,
        name=stock.name,
        market=stock.market,
        industry=stock.industry,
        sub_industry=stock.sub_industry,
        list_date=stock.list_date,
        is_active=stock.is_active,
        total_shares=_f(stock.total_shares),
        latest_financial=summary,
    )

    return APIResponse(data=detail)


def _f(val):
    """安全转换 Decimal → float。"""
    return float(val) if val is not None else None
