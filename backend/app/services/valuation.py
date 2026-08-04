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

    # 行业 β 参考值
    BETA_BY_INDUSTRY = {
        "食品饮料": 0.8, "医药生物": 0.9, "银行": 0.9, "非银金融": 1.0,
        "电子": 1.3, "计算机": 1.3, "电力设备": 1.2, "汽车": 1.1,
        "机械设备": 1.1, "化工": 1.2, "有色金属": 1.2, "国防军工": 1.1,
        "公用事业": 0.7, "交通运输": 0.9, "房地产": 1.0, "建筑装饰": 1.0,
        "传媒": 1.2, "通信": 1.1, "钢铁": 1.1, "煤炭": 1.0,
        "农林牧渔": 1.0, "商贸零售": 1.1, "家用电器": 0.9,
    }
    RISK_FREE_RATE = 0.025   # 无风险利率（十年期国债）
    MARKET_PREMIUM = 0.055   # 市场风险溢价

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

        wacc = request.wacc
        wacc_detail = None
        if wacc == 0.08:  # 默认值，尝试自动计算
            auto_wacc, wacc_detail = self._auto_fill_wacc(request.symbol)
            if auto_wacc:
                wacc = auto_wacc
                params_sources["wacc"] = "auto_filled"
            else:
                params_sources["wacc"] = "default"
        else:
            params_sources["wacc"] = "user_provided"

        # 2. 参数校验
        if fcf_base is None:
            raise ValuationParameterError("无法获取基期自由现金流，请手动提供 fcf_base")
        if total_shares is None or total_shares <= 0:
            raise ValuationParameterError("无法获取总股本，请手动提供 total_shares")

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
            wacc_detail=wacc_detail,
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
        """自动填充总股本。先查 stocks 表，再通过 EPS 反推。"""
        stock = self._get_stock(symbol)
        if stock.total_shares:
            return float(stock.total_shares)
        # 从财报反推：总股本 = 归母净利润 / EPS
        stmt = self._get_latest_stmt(symbol)
        if stmt and stmt.basic_eps and stmt.net_profit_attr_parent:
            eps = float(stmt.basic_eps)
            profit = float(stmt.net_profit_attr_parent)
            if eps > 0:
                return profit / eps
        return None

    def _auto_fill_wacc(self, symbol: str):
        """自动计算 WACC，返回 (wacc值, WaccDetail)。"""
        from app.schemas.valuation import WaccDetail

        detail = WaccDetail()
        stmt = self._get_latest_stmt(symbol)
        if not stmt or not stmt.total_assets or not stmt.total_equity:
            return None, None

        # 权益/负债权重
        equity_weight = float(stmt.total_equity) / float(stmt.total_assets)
        debt_weight = 1 - equity_weight
        detail.equity_weight = round(equity_weight, 4)
        detail.debt_weight = round(debt_weight, 4)

        # 股权成本 = Rf + β × 市场溢价
        stock = self._get_stock(symbol)
        industry = stock.industry if stock and stock.industry else ""
        beta = self.BETA_BY_INDUSTRY.get(industry, 1.0)
        cost_of_equity = self.RISK_FREE_RATE + beta * self.MARKET_PREMIUM
        detail.risk_free_rate = self.RISK_FREE_RATE
        detail.beta = beta
        detail.market_premium = self.MARKET_PREMIUM
        detail.cost_of_equity = round(cost_of_equity, 4)

        # 税后债务成本 = (利息费用 / 有息负债) × (1 - 税率)
        borrowings = (float(stmt.short_term_borrowings or 0) +
                       float(stmt.long_term_borrowings or 0))
        ie = float(stmt.interest_expense or 0)
        cost_of_debt = (ie / borrowings) if borrowings > 0 and ie > 0 else 0.04
        detail.cost_of_debt = round(cost_of_debt, 4)
        # 税率 = 所得税 / 利润总额
        tax_rate = 0.25
        if stmt.total_profit and stmt.total_profit > 0 and stmt.income_tax_expense:
            tax_rate = min(float(stmt.income_tax_expense) / float(stmt.total_profit), 0.35)
        detail.tax_rate = round(tax_rate, 4)

        wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
        detail.wacc = round(max(wacc, 0.03), 4)
        return detail.wacc, detail

    def _auto_fill_dividend(self, symbol: str) -> Optional[float]:
        """自动填充每股股利。先查指标表，再通过 EPS × 30% 估算。"""
        ind = self._get_latest_indicator(symbol)
        if ind and ind.dividend_per_share is not None:
            return float(ind.dividend_per_share)
        # 用 EPS × 30% 估算（A股平均分红率）
        stmt = self._get_latest_stmt(symbol)
        if stmt and stmt.basic_eps:
            eps = float(stmt.basic_eps)
            if eps > 0:
                return eps * 0.3
        return None
