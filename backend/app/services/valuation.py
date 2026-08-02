"""
估值模型计算服务。

DCF 两阶段模型：
    股权价值 = Σ(FCF_t / (1+WACC)^t) + 终值 - 净负债
    每股价值 = 股权价值 / 总股本

DDM 两阶段模型：
    每股价值 = Σ(D_t / (1+r)^t) + 终值现值
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import StockNotFoundException, ValuationParameterError
from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator
from app.schemas.valuation import (
    DCFRequest, DCFResult, DCFResponse,
    DDMRequest, DDMResult, DDMResponse,
)

logger = logging.getLogger(__name__)


class ValuationEngine:
    """估值计算引擎。

    用法：
        engine = ValuationEngine(db)
        result = engine.calculate_dcf(DCFRequest(symbol="600519"))
    """

    def __init__(self, db: Session):
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # DCF 自由现金流折现模型
    # ═══════════════════════════════════════════════════════════
    def calculate_dcf(self, request: DCFRequest) -> DCFResponse:
        """执行 DCF 估值计算。"""
        # 1. 自动填充缺失参数
        params_sources = {}

        fcf_base = request.fcf_base
        if fcf_base is None:
            fcf_base = self._auto_fill_fcf(request.symbol)
            params_sources["fcf_base"] = "auto_filled"
        else:
            params_sources["fcf_base"] = "user_provided"

        net_debt = request.net_debt
        if net_debt is None:
            net_debt = self._auto_fill_net_debt(request.symbol)
            params_sources["net_debt"] = "auto_filled" if net_debt is not None else "unavailable"
        else:
            params_sources["net_debt"] = "user_provided"

        total_shares = request.total_shares
        if total_shares is None:
            total_shares = self._auto_fill_total_shares(request.symbol)
            params_sources["total_shares"] = "auto_filled" if total_shares else "unavailable"
        else:
            params_sources["total_shares"] = "user_provided"

        # 2. 参数校验
        if fcf_base is None:
            raise ValuationParameterError("无法获取基期自由现金流，请手动提供 fcf_base")
        if total_shares is None or total_shares <= 0:
            raise ValuationParameterError("无法获取总股本，请手动提供 total_shares")

        n = request.forecast_years
        g1 = request.growth_rate_stage1
        g2 = request.growth_rate_terminal
        wacc = request.wacc

        if g2 >= wacc:
            raise ValuationParameterError(
                f"永续增长率({g2:.1%}) 必须小于 WACC({wacc:.1%})"
            )

        # 3. 阶段一：逐年折现
        pv_stage1 = 0.0
        for t in range(1, n + 1):
            fcf_t = fcf_base * (1 + g1) ** t
            pv_stage1 += fcf_t / (1 + wacc) ** t

        # 4. 终值（戈登增长模型）
        fcf_terminal = fcf_base * (1 + g1) ** n * (1 + g2)
        terminal_value = fcf_terminal / (wacc - g2)
        pv_terminal = terminal_value / (1 + wacc) ** n

        # 5. 企业价值 → 股权价值
        enterprise_value = pv_stage1 + pv_terminal
        equity_value = enterprise_value - (net_debt or 0)
        fair_value = equity_value / total_shares

        return DCFResponse(
            input_params={
                "fcf_base": fcf_base,
                "fcf_base_source": params_sources["fcf_base"],
                "forecast_years": n,
                "growth_rate_stage1": g1,
                "growth_rate_terminal": g2,
                "wacc": wacc,
                "net_debt": net_debt,
                "net_debt_source": params_sources["net_debt"],
                "total_shares": total_shares,
                "total_shares_source": params_sources["total_shares"],
            },
            result=DCFResult(
                enterprise_value=round(enterprise_value, 2),
                equity_value=round(equity_value, 2),
                fair_value_per_share=round(fair_value, 2),
                pv_stage1=round(pv_stage1, 2),
                pv_terminal=round(pv_terminal, 2),
            ),
        )

    # ═══════════════════════════════════════════════════════════
    # DDM 股利折现模型
    # ═══════════════════════════════════════════════════════════
    def calculate_ddm(self, request: DDMRequest) -> DDMResponse:
        """执行 DDM 估值计算。"""
        params_sources = {}

        d0 = request.d0
        if d0 is None:
            d0 = self._auto_fill_dividend(request.symbol)
            params_sources["d0"] = "auto_filled" if d0 is not None else "unavailable"
        else:
            params_sources["d0"] = "user_provided"

        n = request.forecast_years
        g1 = request.growth_rate_stage1
        g2 = request.growth_rate_terminal
        r = request.required_return

        if d0 is None:
            raise ValuationParameterError("无法获取基期股利，请手动提供 d0")
        if g2 >= r:
            raise ValuationParameterError(
                f"永续增长率({g2:.1%}) 必须小于要求回报率({r:.1%})"
            )

        # 阶段一：逐年折现
        pv_stage1 = 0.0
        for t in range(1, n + 1):
            d_t = d0 * (1 + g1) ** t
            pv_stage1 += d_t / (1 + r) ** t

        # 终值
        d_terminal = d0 * (1 + g1) ** n * (1 + g2)
        terminal_value = d_terminal / (r - g2)
        pv_terminal = terminal_value / (1 + r) ** n

        fair_value = pv_stage1 + pv_terminal

        return DDMResponse(
            input_params={
                "d0": d0,
                "d0_source": params_sources["d0"],
                "forecast_years": n,
                "growth_rate_stage1": g1,
                "growth_rate_terminal": g2,
                "required_return": r,
            },
            result=DDMResult(
                fair_value_per_share=round(fair_value, 2),
                pv_stage1=round(pv_stage1, 2),
                pv_terminal=round(pv_terminal, 2),
            ),
        )

    # ═══════════════════════════════════════════════════════════
    # 自动填充
    # ═══════════════════════════════════════════════════════════
    def _get_latest_stmt(self, symbol: str) -> Optional[FinancialStatement]:
        """获取最新的财务报表。"""
        return (
            self.db.query(FinancialStatement)
            .filter(FinancialStatement.symbol == symbol)
            .order_by(FinancialStatement.report_date.desc())
            .first()
        )

    def _get_latest_indicator(self, symbol: str) -> Optional[FinancialIndicator]:
        """获取最新的计算指标。"""
        return (
            self.db.query(FinancialIndicator)
            .filter(FinancialIndicator.symbol == symbol)
            .order_by(FinancialIndicator.report_date.desc())
            .first()
        )

    def _get_stock(self, symbol: str) -> Stock:
        """获取股票信息，不存在则抛异常。"""
        stock = self.db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise StockNotFoundException(symbol)
        return stock

    def _auto_fill_fcf(self, symbol: str) -> Optional[float]:
        """自动填充自由现金流。

        取最近 3 次年报 FCF 的平均值（避免单年异常波动）。
        financial_indicators 中的 FCF 已经是全年汇总值。
        """
        inds = (
            self.db.query(FinancialIndicator)
            .filter(
                FinancialIndicator.symbol == symbol,
                FinancialIndicator.report_type == "annual",
                FinancialIndicator.fcf.isnot(None),
            )
            .order_by(FinancialIndicator.fiscal_year.desc())
            .limit(3)
            .all()
        )
        if inds:
            values = [float(i.fcf) for i in inds if i.fcf is not None]
            return sum(values) / len(values) if values else None
        return None

    def _auto_fill_net_debt(self, symbol: str) -> Optional[float]:
        """自动填充净负债 = 短期借款 + 长期借款 - 货币资金。"""
        stmt = self._get_latest_stmt(symbol)
        if not stmt:
            return None
        debt = (stmt.short_term_borrowings or 0) + (stmt.long_term_borrowings or 0)
        cash = stmt.cash_and_equivalents or 0
        return float(debt) - float(cash)

    def _auto_fill_total_shares(self, symbol: str) -> Optional[float]:
        """自动填充总股本。"""
        stock = self._get_stock(symbol)
        if stock.total_shares:
            return float(stock.total_shares)
        return None

    def _auto_fill_dividend(self, symbol: str) -> Optional[float]:
        """自动填充每股股利。

        financial_indicators 中的 dividend_per_share 如果是年报已为全年值。
        当前未计算该字段（akshare 季度接口中无直接对应列）。
        """
        ind = self._get_latest_indicator(symbol)
        if ind and ind.dividend_per_share is not None:
            return float(ind.dividend_per_share)
        return None
