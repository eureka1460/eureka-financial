"""
数据入库器。

将清洗后的 DataFrame 批量 upsert 到数据库，
并自动计算 financial_indicators。
"""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.database import SessionLocal
from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator

logger = logging.getLogger(__name__)


class DataLoader:
    """数据入库器。

    用法：
        db = SessionLocal()
        loader = DataLoader(db)
        loader.upsert_stocks(stock_list_df)
        loader.upsert_financials(cleaned_df)
        loader.compute_and_store_indicators("600519")
        db.close()
    """

    def __init__(self, db=None):
        self._db = db
        self._owns_db = False

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
            self._owns_db = True
        return self._db

    def close(self):
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _upsert(self, model, values: dict, unique_cols: list):
        """通用 upsert，兼容 SQLite 和 MySQL。"""
        import math
        # 过滤 NaN 值（MySQL 不接受）
        clean_values = {
            k: (None if isinstance(v, float) and math.isnan(v) else v)
            for k, v in values.items()
        }
        is_mysql = "mysql" in str(self.db.bind.url)
        if is_mysql:
            stmt = mysql_insert(model).values(**clean_values)
            update_cols = {k: stmt.inserted[k] for k in clean_values if k not in ("id", "created_at")}
            stmt = stmt.on_duplicate_key_update(**update_cols)
        else:
            stmt = sqlite_insert(model).values(**clean_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=unique_cols,
                set_={k: stmt.excluded[k] for k in clean_values if k not in ("id", "created_at")},
            )
        self.db.execute(stmt)

    # ── 股票元数据 upsert ─────────────────────────────────
    def upsert_stocks(self, df: pd.DataFrame) -> int:
        """批量 upsert 股票基础信息。

        Args:
            df: 包含 symbol, name 列的 DataFrame

        Returns:
            写入的股票数量
        """
        count = 0
        for _, row in df.iterrows():
            symbol = str(row.get("symbol", "")).strip()
            name = str(row.get("name", "")).strip()
            if not symbol:
                continue

            existing = self.db.query(Stock).filter(Stock.symbol == symbol).first()
            if existing:
                # 更新
                if name:
                    existing.name = name
                existing.updated_at = pd.Timestamp.now()
            else:
                # 插入
                stock = Stock(
                    symbol=symbol,
                    name=name,
                    market=self._guess_market(symbol),
                )
                self.db.add(stock)
            count += 1

        self.db.commit()
        logger.info(f"股票元数据 upsert 完成: {count} 只")
        return count

    @staticmethod
    def _guess_market(symbol: str) -> str:
        """根据股票代码推断交易所。"""
        s = str(symbol).strip()
        if s.startswith("6"):
            return "SH"
        elif s.startswith(("0", "3")):
            return "SZ"
        elif s.startswith(("8", "4")):
            return "BJ"
        return "UNKNOWN"

    # ── 行业分类更新 ────────────────────────────────────
    def upsert_industries(self, df: pd.DataFrame) -> int:
        """批量更新股票的行业分类。"""
        count = 0
        for _, row in df.iterrows():
            symbol = str(row.get("symbol", "")).strip()
            industry = str(row.get("industry", "")).strip()
            if not symbol or not industry:
                continue
            stock = self.db.query(Stock).filter(Stock.symbol == symbol).first()
            if stock and not stock.industry:
                stock.industry = industry
                count += 1
        self.db.commit()
        logger.info(f"行业分类更新: {count} 只")
        return count

    # ── 财务报表 upsert ───────────────────────────────────
    def upsert_financials(self, df: pd.DataFrame) -> int:
        """批量 upsert 财务报表数据。

        使用 SQLite 的 INSERT ... ON CONFLICT ... DO UPDATE，
        按 (symbol, report_date, report_type) 唯一键去重。

        Args:
            df: 清洗后的合并宽表 DataFrame

        Returns:
            upsert 行数
        """
        if df is None or len(df) == 0:
            return 0

        records = df.to_dict(orient="records")
        count = 0
        skipped = 0

        for record in records:
            try:
                # 跳过缺少关键字段的行
                symbol = record.get("symbol")
                report_date = record.get("report_date")
                report_type = record.get("report_type")
                if not symbol or not report_date or not report_type:
                    skipped += 1
                    continue

                self._upsert(
                    FinancialStatement, record,
                    unique_cols=["symbol", "report_date", "report_type"],
                )
                count += 1

            except Exception as e:
                logger.error(f"upsert 失败: {record.get('symbol', '?')} "
                             f"{record.get('report_date', '?')}: {e}")

        self.db.commit()
        logger.info(f"财务报表 upsert 完成: {count} 行 (跳过 {skipped} 行)")
        return count

    # ── 计算指标 ──────────────────────────────────────────
    def compute_and_store_indicators(self, symbol: str) -> int:
        """为指定股票计算并存储年度指标。

        仅对年报（report_type='annual'）计算指标。
        年报的利润表和现金流数据使用该财年四个季度的汇总值，
        资产负债表使用 Q4 年报时点值。
        """
        # 获取所有报表
        all_stmts = (
            self.db.query(FinancialStatement)
            .filter(FinancialStatement.symbol == symbol)
            .order_by(FinancialStatement.report_date.asc())
            .all()
        )

        if not all_stmts:
            logger.warning(f"{symbol}: 无财务数据")
            return 0

        # 按财年汇总季度数据
        fy_quarters = {}
        for s in all_stmts:
            fy = s.fiscal_year
            if fy not in fy_quarters:
                fy_quarters[fy] = []
            fy_quarters[fy].append(s)

        # 构建上年指标映射（用于 YoY）
        prev_map = {}

        # 仅计算年报指标
        annuals = [s for s in all_stmts if s.report_type == "annual"]
        count = 0
        for s in annuals:
            try:
                fy = s.fiscal_year
                quarters = fy_quarters.get(fy, [])

                # 构建全年汇总（用四个季度之和）
                annual_stmt = self._build_annual_from_quarters(s, quarters)

                # 上年年报 ORM（用于 YoY 对比）
                prev_key = (fy - 1, "annual")
                prev_annual_stmt = prev_map.get(prev_key)

                indicators = self._compute_annual_indicators(
                    annual_stmt, quarters, prev_annual_stmt, prev_annual_data=None
                )
                if indicators:
                    self._upsert_indicator(indicators)
                    prev_map[(fy, "annual")] = s
                    count += 1
            except Exception as e:
                logger.error(f"{symbol} FY{s.fiscal_year} 指标计算失败: {e}")

        self.db.commit()
        logger.info(f"{symbol}: 指标计算完成，{count} 条年报")
        return count

    def _build_annual_from_quarters(
        self, annual_stmt: FinancialStatement, quarters: list
    ) -> dict:
        """用四个季度之和构建全年利润表和现金流数据。

        Returns:
            包含 annualized 数据的 dict，用于指标计算。
        """
        result = {
            "stmt": annual_stmt,
            "operating_revenue": 0.0,
            "operating_cost": 0.0,
            "operating_profit": 0.0,
            "total_profit": 0.0,
            "net_profit": 0.0,
            "net_profit_attr_parent": 0.0,
            "net_profit_excl_nonrecurring": 0.0,
            "net_operating_cashflow": 0.0,
            "net_investing_cashflow": 0.0,
            "net_financing_cashflow": 0.0,
            "capital_expenditure": 0.0,
            "dividends_paid": 0.0,
        }

        for q in quarters:
            result["operating_revenue"] += self._f(q.operating_revenue) or 0
            result["operating_cost"] += self._f(q.operating_cost) or 0
            result["operating_profit"] += self._f(q.operating_profit) or 0
            result["total_profit"] += self._f(q.total_profit) or 0
            result["net_profit"] += self._f(q.net_profit) or 0
            result["net_profit_attr_parent"] += self._f(q.net_profit_attr_parent) or 0
            result["net_profit_excl_nonrecurring"] += self._f(q.net_profit_excl_nonrecurring) or 0
            result["net_operating_cashflow"] += self._f(q.net_operating_cashflow) or 0
            result["net_investing_cashflow"] += self._f(q.net_investing_cashflow) or 0
            result["net_financing_cashflow"] += self._f(q.net_financing_cashflow) or 0
            result["capital_expenditure"] += self._f(q.capital_expenditure) or 0
            result["dividends_paid"] += self._f(q.dividends_paid) or 0

        return result

    @staticmethod
    def _f(val):
        """将 Decimal 安全转换为 float，None 返回 None。"""
        if val is None:
            return None
        return float(val)

    def _compute_annual_indicators(
        self,
        annual: dict,
        quarters: list,
        prev_annual_stmt,
        prev_annual_data: dict = None,
    ) -> Optional[dict]:
        """用全年汇总数据计算年度衍生指标。

        Args:
            annual: _build_annual_from_quarters 返回的年度汇总 dict
            quarters: 该财年所有季度报表列表
            prev_annual_stmt: 上年年报的 FinancialStatement ORM 对象
            prev_annual_data: 上年年度汇总 dict（用于 P&L / 现金流 YoY）
        """
        s = annual["stmt"]  # 年报 FinancialStatement

        ind = {
            "symbol": s.symbol,
            "report_date": s.report_date,
            "report_type": "annual",
            "fiscal_year": s.fiscal_year,
        }

        # _by_report_em 中 Q4 年报即为全年累计值，直接使用
        rev = self._f(s.operating_revenue) or 0
        cost = self._f(s.operating_cost) or 0
        op_profit = self._f(s.operating_profit) or 0
        total_profit = self._f(s.total_profit) or 0
        net_p = self._f(s.net_profit) or 0
        net_p_attr = self._f(s.net_profit_attr_parent) or 0
        ocf = self._f(s.net_operating_cashflow) or 0
        capex = self._f(s.capital_expenditure) or 0

        # ── 盈利能力 ──
        if net_p_attr != 0 and s.total_equity:
            e1 = self._f(s.total_equity)
            e0 = self._f(prev_annual_stmt.total_equity) if prev_annual_stmt and prev_annual_stmt.total_equity else None
            avg_equity = (e1 + e0) / 2 if e0 else e1
            if avg_equity > 0:
                ind["roe"] = net_p_attr / avg_equity

        if net_p != 0 and s.total_assets:
            a1 = self._f(s.total_assets)
            a0 = self._f(prev_annual_stmt.total_assets) if prev_annual_stmt and prev_annual_stmt.total_assets else None
            avg_assets = (a1 + a0) / 2 if a0 else a1
            if avg_assets > 0:
                ind["roa"] = net_p / avg_assets

        if rev > 0:
            ind["gross_margin"] = (rev - cost) / rev
            ind["net_margin"] = net_p_attr / rev
            if op_profit != 0:
                ind["operating_margin"] = op_profit / rev

        # ── 成长能力 ──（直接从上年 ORM 取全年值，_by_report_em 中 Q4 = 全年）
        if prev_annual_stmt:
            prev_rev = self._f(prev_annual_stmt.operating_revenue) or 0
            prev_profit = self._f(prev_annual_stmt.net_profit_attr_parent) or 0
            prev_op = self._f(prev_annual_stmt.operating_profit) or 0

            if prev_rev > 0 and rev > 0:
                ind["revenue_yoy"] = (rev - prev_rev) / prev_rev
            if prev_profit > 0 and net_p_attr > 0:
                ind["net_profit_yoy"] = (net_p_attr - prev_profit) / prev_profit
            if prev_op > 0 and op_profit > 0:
                ind["operating_profit_yoy"] = (op_profit - prev_op) / prev_op

        # ── 偿债与流动性（用年报时点数据）──
        if s.current_assets and s.current_liabilities and s.current_liabilities > 0:
            ind["current_ratio"] = self._f(s.current_assets) / self._f(s.current_liabilities)

        # 速动比率 = (货币资金 + 交易性金融资产 + 应收票据 + 应收账款 + 其他应收款) / 流动负债
        if s.current_liabilities and s.current_liabilities > 0:
            quick_num = (
                (self._f(s.cash_and_equivalents) or 0)
                + (self._f(s.trading_financial_assets) or 0)
                + (self._f(s.notes_receivable) or 0)
                + (self._f(s.accounts_receivable) or 0)
                + (self._f(s.other_receivables) or 0)
            )
            ind["quick_ratio"] = quick_num / self._f(s.current_liabilities)

        if s.total_liabilities and s.total_assets and s.total_assets > 0:
            ind["debt_to_assets"] = self._f(s.total_liabilities) / self._f(s.total_assets)

        if s.total_liabilities and s.total_equity and s.total_equity > 0:
            ind["debt_to_equity"] = self._f(s.total_liabilities) / self._f(s.total_equity)

        ie = self._f(s.interest_expense)
        if ie and ie != 0 and op_profit != 0:
            ind["interest_coverage"] = op_profit / abs(ie)

        # ── 营运效率 ──
        if rev > 0 and s.total_assets and s.total_assets > 0:
            a1 = self._f(s.total_assets)
            a0 = self._f(prev_annual_stmt.total_assets) if prev_annual_stmt and prev_annual_stmt.total_assets else None
            avg_assets = (a1 + a0) / 2 if a0 else a1
            ind["asset_turnover"] = rev / avg_assets

        # ── 估值相关 ──
        ind["fcf"] = ocf - capex

        if s.total_equity:
            stock = self.db.query(Stock).filter(Stock.symbol == s.symbol).first()
            if stock and stock.total_shares and stock.total_shares > 0:
                ind["book_value_per_share"] = self._f(s.total_equity) / self._f(stock.total_shares)
                # 每股股利 = 全年股利支出 / 总股本
                total_div = annual.get("dividends_paid", 0) or 0
                if total_div > 0:
                    ind["dividend_per_share"] = total_div / self._f(stock.total_shares)

        # ── 单季度值清空（年报不需要） ──
        ind["revenue_single_q"] = None
        ind["net_profit_single_q"] = None
        ind["operating_cashflow_single_q"] = None

        return ind if len(ind) > 5 else None

    def _upsert_indicator(self, ind: dict):
        """插入或更新一条计算指标记录。"""
        self._upsert(
            FinancialIndicator, ind,
            unique_cols=["symbol", "report_date", "report_type"],
        )

    # ── 清空数据（用于重置） ──────────────────────────────
    def truncate_all(self):
        """清空所有财务数据（保留 stocks 表）。"""
        self.db.query(FinancialIndicator).delete()
        self.db.query(FinancialStatement).delete()
        self.db.commit()
        logger.warning("已清空 financial_statements 和 financial_indicators 表")
