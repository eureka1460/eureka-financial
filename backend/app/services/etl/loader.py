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


# 同花顺财务摘要中的这些字段以“百分数”返回，例如 -112.20 表示
# -112.20%，数据库统一存为小数 -1.122，供前端 fmtPercent 使用。
# 流动比率、速动比率和周转率是“倍数”，不能参与百分比换算。
THS_PERCENT_FIELDS = frozenset({
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "operating_margin",
    "revenue_yoy",
    "net_profit_yoy",
    "operating_profit_yoy",
    "debt_to_assets",
    "debt_to_equity",
})


def normalize_ths_indicator_value(db_field: str, raw) -> float:
    """将同花顺指标转换为数据库统一口径。"""
    value = float(
        str(raw).strip()
        .replace("%", "")
        .replace("亿", "")
        .replace("万", "")
        .replace("元", "")
    )
    if db_field in THS_PERCENT_FIELDS:
        value /= 100
    return round(value, 6)


def calculate_free_cash_flow(operating_cashflow, capital_expenditure):
    """FCF = 经营活动现金流量净额 - 资本性支出。

    资本性支出使用“购建固定资产、无形资产和其他长期资产支付的现金”。
    两项任一缺失时不进行猜测，返回 None。
    """
    if operating_cashflow is None or capital_expenditure is None:
        return None
    return float(operating_cashflow) - abs(float(capital_expenditure))


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

    # ── 指标获取（直接从 akshare 同花顺预计算接口）─────────
    def compute_and_store_indicators(self, symbol: str) -> int:
        """从 akshare 同花顺接口获取预计算财务指标，直接入库。

        同花顺已预计算：ROE/ROA/毛利率/净利率/流动比率/速动比率/
        保守速动比率/资产负债率/权益乘数/每股净资产/EPS/存货周转率/
        应收账款周转率/YoY增长率等，无需自行计算。
        """
        try:
            import akshare as ak
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator='按报告期')
        except Exception as e:
            import traceback
            logger.error(f"{symbol}: 同花顺指标抓取失败: {e}\n{traceback.format_exc()}")
            return 0

        if df is None or len(df) == 0:
            return 0

        # 列名映射：中文列名 → 数据库字段
        col_map = {
            '报告期': '_date',
            '净资产收益率': 'roe',
            '总资产收益率': 'roa',
            '销售毛利率': 'gross_margin',
            '销售净利率': 'net_margin',
            '营业利润率': 'operating_margin',
            '营业收入同比增长率': 'revenue_yoy',
            '净利润同比增长率': 'net_profit_yoy',
            '营业利润同比增长率': 'operating_profit_yoy',
            '流动比率': 'current_ratio',
            '速动比率': 'quick_ratio',
            '资产负债率': 'debt_to_assets',
            '产权比率': 'debt_to_equity',
            '存货周转率': 'inventory_turnover',
            '应收账款周转率': 'receivable_turnover',
            '总资产周转率': 'asset_turnover',
            '每股净资产': 'book_value_per_share',
        }

        from datetime import datetime as dt, date as dt_date
        current_year = dt.now().year
        count = 0
        for _, row in df.iterrows():
            try:
                date_str = str(row.get('报告期', ''))
                if len(date_str) < 10:
                    continue

                rd = dt.strptime(date_str[:10], '%Y-%m-%d').date()
                fy = rd.year
                if fy < current_year - 5:
                    continue

                # 推断 report_type
                m = rd.month
                d = rd.day
                if m == 12 and d == 31: rt = 'annual'
                elif m == 9 and d == 30: rt = 'q3'
                elif m == 6 and d == 30: rt = 'semi_annual'
                elif m == 3 and d == 31: rt = 'q1'
                else: continue

                ind = {
                    'symbol': symbol,
                    'report_date': rd,
                    'report_type': rt,
                    'fiscal_year': fy,
                }

                # 列名标准化（兼容不同编码）
                row_keys = set(str(k).strip() for k in row.index)
                for cn_col, db_field in col_map.items():
                    if db_field == '_date':
                        continue
                    cn_key = str(cn_col).strip()
                    if cn_key not in row_keys:
                        continue
                    raw = row[cn_col]
                    if raw is None or raw is False:
                        continue
                    s = str(raw).strip()
                    if s in ('', 'nan', 'False', 'None'):
                        continue
                    try:
                        ind[db_field] = normalize_ths_indicator_value(db_field, s)
                    except (ValueError, TypeError):
                        pass

                if len(ind) > 4:
                    self._upsert_indicator(ind)
                    count += 1
            except Exception as e:
                logger.error(f"{symbol} {date_str} 指标入库失败: {e}")

        self.db.commit()
        # FCF = 经营CF - 资本性支出，存到年报指标里。
        # 投资活动现金流净额包含理财投资和投资回收，不能代替资本性支出。
        try:
            stmts = (
                self.db.query(FinancialStatement)
                .filter(
                    FinancialStatement.symbol == symbol,
                    FinancialStatement.report_type == 'annual',
                )
                .order_by(FinancialStatement.report_date.desc())
                .all()
            )
            for stmt in stmts:
                fcf = calculate_free_cash_flow(
                    stmt.net_operating_cashflow,
                    stmt.capital_expenditure,
                )
                # 即使当前缺少资本开支，也要写入 NULL，清除旧版本按错误
                # 口径计算出的 FCF，避免估值继续读取脏数据。
                self._upsert_indicator({
                    'symbol': symbol, 'report_date': stmt.report_date,
                    'report_type': 'annual', 'fiscal_year': stmt.fiscal_year,
                    'fcf': fcf,
                })
            self.db.commit()
        except Exception as e:
            logger.error(f"{symbol} FCF 计算失败: {e}")

        logger.info(f"{symbol}: 同花顺指标入库 {count} 条")
        return count

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
