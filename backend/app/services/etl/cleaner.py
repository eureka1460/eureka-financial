"""
数据清洗器。

对 akshare 原始 DataFrame 执行：
1. 列名映射（中文 → 英文）
2. 单位检测与统一（万元 → 元）
3. 空值处理（NaN → None）
4. report_date 解析与 report_type 推断
5. 数据校验（总资产 > 0，会计恒等式检查）
6. 仅保留数据库需要的列
"""

import logging
from datetime import datetime, date

import pandas as pd
import numpy as np

from app.core.exceptions import DataValidationException
from app.services.etl.column_mapping import get_mapping

logger = logging.getLogger(__name__)

# ── 数据库字段列表（仅保留这些列）──────────────────────────
# 从 financial_statements 模型中提取所有数据字段
DB_COLUMNS = [
    "symbol", "report_date", "report_type", "fiscal_year",
    "currency", "data_source",
    # 资产负债表-资产
    "total_assets", "current_assets", "cash_and_equivalents",
    "trading_financial_assets", "notes_receivable", "accounts_receivable",
    "prepayments", "other_receivables", "inventory",
    "non_current_assets", "fixed_assets", "construction_in_progress",
    "intangible_assets", "goodwill", "long_term_equity_investments",
    "deferred_tax_assets",
    # 资产负债表-负债
    "total_liabilities", "current_liabilities", "short_term_borrowings",
    "notes_payable", "accounts_payable", "contract_liabilities",
    "employee_payable", "taxes_payable", "non_current_liabilities",
    "long_term_borrowings", "bonds_payable", "deferred_tax_liabilities",
    # 资产负债表-权益
    "total_equity", "paid_in_capital", "capital_reserve",
    "surplus_reserve", "retained_earnings", "minority_interest",
    # 利润表
    "operating_revenue", "operating_cost", "selling_expenses",
    "administrative_expenses", "r_and_d_expenses", "financial_expenses",
    "interest_expense", "investment_income", "fair_value_change",
    "asset_impairment_loss", "credit_impairment_loss",
    "taxes_and_surcharges", "operating_profit", "total_profit",
    "income_tax_expense", "net_profit", "net_profit_attr_parent",
    "net_profit_excl_nonrecurring", "minority_profit",
    "basic_eps", "diluted_eps", "other_comprehensive_income",
    # 现金流量表
    "net_operating_cashflow", "cash_from_sales",
    "cash_paid_to_employees", "taxes_paid",
    "net_investing_cashflow", "capital_expenditure",
    "net_financing_cashflow", "cash_from_borrowings",
    "dividends_paid", "net_change_in_cash",
    "beginning_cash_balance", "ending_cash_balance",
]


class DataCleaner:
    """数据清洗器。

    用法：
        cleaner = DataCleaner()
        clean_df = cleaner.clean_balance_sheet(raw_df, symbol="600519")
    """

    # ── 单位检测阈值 ──────────────────────────────────────
    # 如果中位数总资产超过此值，判定单位是"万元"而非"元"
    UNIT_THRESHOLD = 1e12  # A 股最大公司总资产约 40 万亿 = 4e13 元

    # ── 校验容忍度 ────────────────────────────────────────
    BALANCE_TOLERANCE = 0.01  # 资产负债表不平衡的容忍度 1%

    # ── 清洗主入口 ────────────────────────────────────────
    def clean_balance_sheet(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """清洗资产负债表。"""
        return self._clean(df, symbol, "balance_sheet", source="eastmoney")

    def clean_income_statement(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """清洗利润表。"""
        return self._clean(df, symbol, "income_statement", source="eastmoney")

    def clean_cash_flow(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """清洗现金流量表。"""
        return self._clean(df, symbol, "cash_flow", source="eastmoney")

    # ── 通用清洗流程 ──────────────────────────────────────
    def _clean(
        self,
        df: pd.DataFrame,
        symbol: str,
        sheet_type: str,
        source: str = "eastmoney",
    ) -> pd.DataFrame:
        """执行完整的清洗流水线。"""
        if df is None or len(df) == 0:
            raise DataValidationException(
                symbol=symbol,
                detail=f"{sheet_type} 数据为空",
            )

        df = df.copy()

        # 步骤 1: 列名映射
        df = self._map_columns(df, sheet_type)

        # 步骤 2: 单位检测与转换
        df = self._normalize_units(df, sheet_type)

        # 步骤 3: 空值处理
        df = self._handle_nulls(df)

        # 步骤 4: 日期解析与报表类型推断
        df = self._parse_report_date(df)

        # 步骤 5: 添加元数据列
        df["symbol"] = symbol
        df["data_source"] = source
        df["currency"] = "CNY"

        # 步骤 6: 仅保留数据库需要的列
        df = self._filter_columns(df)

        # 步骤 7: 数据校验
        if sheet_type == "balance_sheet":
            self._validate_balance_sheet(df, symbol)

        logger.info(
            f"{symbol}: {sheet_type} 清洗完成，"
            f"共 {len(df)} 个报表期"
        )

        return df

    # ── 步骤 1: 列名映射 ──────────────────────────────────
    def _map_columns(self, df: pd.DataFrame, sheet_type: str) -> pd.DataFrame:
        """将 akshare 中文列名映射为数据库英文字段名。"""
        mapping = get_mapping(sheet_type)
        # 只重命名存在的列
        rename_dict = {k: v for k, v in mapping.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        if not rename_dict:
            logger.warning(f"列名映射无匹配！原始列名: {list(df.columns)[:10]}")
        return df

    # ── 步骤 2: 单位检测与转换 ────────────────────────────
    def _normalize_units(self, df: pd.DataFrame, sheet_type: str) -> pd.DataFrame:
        """检测并统一金额单位为元。

        akshare 东方财富接口返回的数据单位通常是"元"，
        但为防异常，检查关键字段的数值范围。
        """
        # 用总资产（或营收）的中位数判断单位
        check_col = None
        if "total_assets" in df.columns:
            check_col = "total_assets"
        elif "operating_revenue" in df.columns:
            check_col = "operating_revenue"

        if check_col:
            col_data = df[check_col]
            # 如果有多个同名列，取第一列
            if isinstance(col_data, pd.DataFrame):
                col_data = col_data.iloc[:, 0]
            median_val = col_data.dropna().median()
            if pd.notna(median_val) and median_val > self.UNIT_THRESHOLD:
                logger.warning(
                    f"检测到疑似万元单位: {check_col} 中位数={median_val:.0f} "
                    f"超过阈值 {self.UNIT_THRESHOLD:.0f}，自动 x10000 转换为元"
                )
                # 所有数值列 x 10000
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                df[numeric_cols] = df[numeric_cols] * 10000

        return df

    # ── 步骤 3: 空值处理 ──────────────────────────────────
    @staticmethod
    def _handle_nulls(df: pd.DataFrame) -> pd.DataFrame:
        """pandas NaN → None（SQL NULL）。"""
        return df.where(pd.notnull(df), None)

    # ── 步骤 4: 日期解析与报表类型推断 ────────────────────
    @staticmethod
    def _parse_report_date(df: pd.DataFrame) -> pd.DataFrame:
        """解析 report_date 并推断 report_type 和 fiscal_year。

        akshare 返回的日期可能是：
        - "2024-12-31" (字符串)
        - datetime.date 对象
        - "20241231" (数字格式)
        """
        if "report_date" not in df.columns:
            raise DataValidationException(detail="数据缺少 report_date 列")

        # 统一转换为 date 对象
        def _parse_date(val):
            if val is None:
                return None
            if isinstance(val, date) and not isinstance(val, datetime):
                return val
            if isinstance(val, datetime):
                return val.date()
            s = str(val).strip()
            # 截断时间部分: "2026-03-31 00:00:00" → "2026-03-31"
            if " " in s:
                s = s.split()[0]
            for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(s, fmt).date()
                except ValueError:
                    continue
            if len(s) == 4 and s.isdigit():
                return date(int(s), 12, 31)
            return None

        df["report_date"] = df["report_date"].apply(_parse_date)

        # 推断 report_type
        def _infer_type(d: date) -> str:
            if d is None:
                return "annual"
            m = d.month
            d_day = d.day
            if m == 12 and d_day == 31:
                return "annual"
            elif m == 6 and d_day == 30:
                return "semi_annual"
            elif m == 3 and d_day == 31:
                return "q1"
            elif m == 9 and d_day == 30:
                return "q3"
            # 备用：按月份推断
            elif m <= 3:
                return "q1"
            elif m <= 6:
                return "semi_annual"
            elif m <= 9:
                return "q3"
            else:
                return "annual"

        df["report_type"] = df["report_date"].apply(_infer_type)

        # 推断 fiscal_year
        df["fiscal_year"] = df["report_date"].apply(
            lambda d: d.year if d else None
        )

        return df

    # ── 步骤 5: 过滤列 ────────────────────────────────────
    @staticmethod
    def _filter_columns(df: pd.DataFrame) -> pd.DataFrame:
        """仅保留数据库中存在的列，丢弃 akShare 返回的额外字段。"""
        keep_cols = [c for c in DB_COLUMNS if c in df.columns]
        return df[keep_cols]

    # ── 步骤 6: 数据校验 ──────────────────────────────────
    def _validate_balance_sheet(self, df: pd.DataFrame, symbol: str):
        """校验资产负债表数据的合理性。"""
        issues = []

        for idx, row in df.iterrows():
            rpt_date = row.get("report_date", "?")

            # 总资产必须 > 0
            ta = row.get("total_assets")
            if ta is not None and ta <= 0:
                issues.append(f"{rpt_date}: total_assets={ta} (应 > 0)")

            # 会计恒等式：|总资产 − 总负债 − 净资产| / 总资产 < 1%
            tl = row.get("total_liabilities")
            te = row.get("total_equity")
            if ta is not None and tl is not None and te is not None and ta > 0:
                diff = abs(ta - tl - te)
                if diff / ta > self.BALANCE_TOLERANCE:
                    issues.append(
                        f"{rpt_date}: 资产负债不平衡 "
                        f"(资产={ta:.0f}, 负债={tl:.0f}, 权益={te:.0f}, "
                        f"差额={diff:.0f}, 偏差={diff/ta*100:.2f}%)"
                    )

        if issues:
            logger.warning(f"{symbol}: 资产负债表校验发现 {len(issues)} 个问题")
            for issue in issues[:5]:  # 只打印前 5 条
                logger.warning(f"  {issue}")

    # ── 合并三张表 ────────────────────────────────────────
    def merge_statements(
        self,
        balance_df: pd.DataFrame,
        income_df: pd.DataFrame,
        cashflow_df: pd.DataFrame,
        symbol: str,
    ) -> pd.DataFrame:
        """将三张清洗后的报表按 (symbol, report_date) 合并为宽表的一行。

        三张表有重叠的元数据列（symbol, report_date, report_type, fiscal_year 等），
        合并时以资产负债表为基准，利润表和现金流量表仅保留独有的数据列。

        Returns:
            合并后的 DataFrame，每行是一个完整的 financial_statement 记录。
        """
        # 定义合并键
        merge_keys = ["symbol", "report_date", "report_type", "fiscal_year"]

        # 识别每张表的数据列（去掉合并键和通用元数据列）
        key_cols = set(merge_keys + ["data_source", "currency", "created_at", "updated_at"])

        def _get_data_cols(df, prefix):
            return [c for c in df.columns if c not in key_cols]

        # 利润表：只保留数据列 + 合并键
        income_data_cols = _get_data_cols(income_df, "income")
        income_for_merge = income_df[merge_keys + income_data_cols]

        # 现金流量表：只保留数据列 + 合并键
        cf_data_cols = _get_data_cols(cashflow_df, "cf")
        cf_for_merge = cashflow_df[merge_keys + cf_data_cols]

        # 三步合并：以资产负债表为基准
        merged = balance_df.merge(
            income_for_merge,
            on=merge_keys,
            how="left",
        )
        merged = merged.merge(
            cf_for_merge,
            on=merge_keys,
            how="left",
        )

        logger.info(f"{symbol}: 三表合并完成，共 {len(merged)} 个完整报表期")

        return merged
