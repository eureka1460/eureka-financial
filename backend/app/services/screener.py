"""
筛选引擎。

将用户构造的条件 JSON 翻译为 SQLAlchemy 查询，
逐只股票检查"最近 N 份同类报表是否全部满足条件"，
最后取 AND/OR 组合返回符合条件的股票列表。
"""

import re
import logging
from typing import Optional

from sqlalchemy import and_, or_, func as sql_func, literal_column
from sqlalchemy.orm import Session

from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator
from app.schemas.screener import ScreenerRequest, ScreenerResultItem, MatchDetail

logger = logging.getLogger(__name__)

# ── 已知的合法字段名（financial_statements + financial_indicators）──
VALID_METRICS = {
    # 资产负债表
    "total_assets", "current_assets", "cash_and_equivalents",
    "accounts_receivable", "inventory", "fixed_assets", "goodwill",
    "intangible_assets", "total_liabilities", "current_liabilities",
    "short_term_borrowings", "long_term_borrowings", "total_equity",
    "retained_earnings",
    # 利润表
    "operating_revenue", "operating_cost", "selling_expenses",
    "administrative_expenses", "r_and_d_expenses", "financial_expenses",
    "interest_expense", "operating_profit", "total_profit",
    "net_profit", "net_profit_attr_parent", "net_profit_excl_nonrecurring",
    "basic_eps", "diluted_eps",
    # 现金流量表
    "net_operating_cashflow", "net_investing_cashflow",
    "net_financing_cashflow", "capital_expenditure",
    "dividends_paid", "ending_cash_balance",
    # 计算指标
    "roe", "roa", "gross_margin", "net_margin", "operating_margin",
    "revenue_yoy", "net_profit_yoy", "operating_profit_yoy", "eps_yoy",
    "current_ratio", "quick_ratio", "debt_to_assets", "debt_to_equity",
    "interest_coverage", "asset_turnover",
    "fcf", "dividend_per_share", "book_value_per_share",
}

# ── 判断字段属于哪张表 ──
INDICATOR_FIELDS = {
    "roe", "roa", "gross_margin", "net_margin", "operating_margin",
    "revenue_yoy", "net_profit_yoy", "operating_profit_yoy", "eps_yoy",
    "current_ratio", "quick_ratio", "debt_to_assets", "debt_to_equity",
    "interest_coverage", "asset_turnover",
    "fcf", "dividend_per_share", "book_value_per_share",
}


def _get_column(table, field: str):
    """根据字段名返回对应的 SQLAlchemy Column 对象。"""
    if field in INDICATOR_FIELDS:
        return getattr(FinancialIndicator, field)
    return getattr(FinancialStatement, field)


def _parse_expression(expr_str: str):
    """将用户表达式中的变量名替换为 SQLAlchemy Column 引用。

    例:
        "(net_operating_cashflow - capital_expenditure) / net_profit_attr_parent"
    → 返回一个 SQLAlchemy 表达式对象，可直接用于 query.filter()。

    实现策略：
        识别表达式中的变量 token，替换为对应表的 column 引用。
        但 SQLite 不支持按 expression alias 过滤，
        因此改用 Python 计算方式：查询出原始值后在 Python 中计算。
    """
    # 提取表达式中的所有变量名
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr_str)

    # 过滤出合法的字段名
    fields = {}
    for t in tokens:
        if t.lower() in VALID_METRICS:
            fields[t.lower()] = t

    # 关键字过滤
    keywords = {"and", "or", "not", "null", "true", "false", "abs"}
    fields = {k: v for k, v in fields.items() if k not in keywords}

    return fields


class ScreenerEngine:
    """选股筛选引擎。"""

    # 运算符映射
    OP_MAP = {
        ">": lambda col, val: col > val,
        ">=": lambda col, val: col >= val,
        "<": lambda col, val: col < val,
        "<=": lambda col, val: col <= val,
        "==": lambda col, val: col == val,
        "!=": lambda col, val: col != val,
    }

    def __init__(self, db: Session):
        self.db = db

    def search(self, request: ScreenerRequest) -> dict:
        """执行筛选查询。

        Returns:
            {"items": [...], "total": int, "page": int, "page_size": int}
        """
        # 1. 对每个条件筛选出一组股票代码
        candidate_sets = []
        for i, cond in enumerate(request.conditions):
            candidates = self._evaluate_condition(cond, request.report_type)
            candidate_sets.append(candidates)
            logger.info(
                f"条件 {i+1}: {cond.metric or cond.expression[:30]} "
                f"{cond.operator} {cond.value} "
                f"(连续{cond.consecutive_years}年) → {len(candidates)} 只"
            )

        # 2. 取 AND/OR 组合
        if request.logic == "AND":
            if candidate_sets:
                matched_symbols = candidate_sets[0]
                for s in candidate_sets[1:]:
                    matched_symbols = matched_symbols & s
            else:
                matched_symbols = set()
        else:  # OR
            matched_symbols = set()
            for s in candidate_sets:
                matched_symbols = matched_symbols | s

        # 3. 行业筛选
        if request.industry_filter:
            industry_stocks = {
                s.symbol
                for s in self.db.query(Stock.symbol)
                .filter(Stock.industry.in_(request.industry_filter))
                .all()
            }
            matched_symbols = matched_symbols & industry_stocks

        # 4. 查询股票信息并分页
        all_matched = sorted(matched_symbols)
        total = len(all_matched)

        offset = (request.page - 1) * request.page_size
        page_symbols = all_matched[offset : offset + request.page_size]

        # 5. 构建响应
        items = []
        for symbol in page_symbols:
            stock = self.db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                continue

            # 获取最新指标值
            latest_ind = (
                self.db.query(FinancialIndicator)
                .filter(FinancialIndicator.symbol == symbol)
                .order_by(FinancialIndicator.report_date.desc())
                .first()
            )

            latest_vals = {}
            if latest_ind:
                for cond in request.conditions:
                    metric = cond.metric
                    if metric and hasattr(latest_ind, metric):
                        v = getattr(latest_ind, metric)
                        latest_vals[metric] = float(v) if v is not None else None

            items.append(
                ScreenerResultItem(
                    symbol=stock.symbol,
                    name=stock.name,
                    industry=stock.industry,
                    match_detail=MatchDetail(
                        latest_values=latest_vals,
                        conditions_passed=len(request.conditions),
                        conditions_total=len(request.conditions),
                    ),
                )
            )

        return {
            "items": items,
            "total": total,
            "page": request.page,
            "page_size": request.page_size,
        }

    def _evaluate_condition(
        self, cond, report_type: str
    ) -> set[str]:
        """评估单条条件，返回满足条件的股票代码集合。"""
        if cond.metric:
            return self._evaluate_metric_condition(
                cond.metric, cond.operator, cond.value,
                cond.consecutive_years, report_type,
            )
        elif cond.expression:
            return self._evaluate_expression_condition(
                cond.expression, cond.operator, cond.value,
                cond.consecutive_years, report_type,
            )
        return set()

    def _evaluate_metric_condition(
        self, metric: str, operator: str, value: float,
        consecutive_years: int, report_type: str,
    ) -> set[str]:
        """评估单指标条件。

        对每只股票，获取最近 consecutive_years 条符合 report_type 的报表，
        检查是否全部满足 metric operator value。
        """
        if metric not in VALID_METRICS:
            raise ValueError(f"未知指标: {metric}")

        col = _get_column(metric, metric)
        op_fn = self.OP_MAP.get(operator)
        if not op_fn:
            raise ValueError(f"不支持的运算符: {operator}")

        # 判断需要查哪张表
        if metric in INDICATOR_FIELDS:
            model = FinancialIndicator
        else:
            model = FinancialStatement

        # 获取所有股票的最新 N 条报表
        # 策略：用子查询 + 窗口函数
        from sqlalchemy import text as sa_text

        # 构建筛选条件
        filter_expr = op_fn(col, value)

        # 子查询：每只股票的每期报表，按日期降序排号
        rn_subq = (
            self.db.query(
                model.symbol,
                model.report_date,
                sql_func.row_number()
                .over(
                    partition_by=model.symbol,
                    order_by=model.report_date.desc(),
                )
                .label("rn"),
            )
            .filter(
                model.report_type == report_type,
                filter_expr,
            )
            .subquery()
        )

        # 对于每只股票，统计前 N 条中满足条件的数量
        # 如果 count == consecutive_years，则该股票通过
        matched = self.db.query(rn_subq.c.symbol).filter(
            rn_subq.c.rn <= consecutive_years
        ).group_by(rn_subq.c.symbol).having(
            sql_func.count() == consecutive_years
        ).all()

        return {m[0] for m in matched}

    def _evaluate_expression_condition(
        self, expression: str, operator: str, value: float,
        consecutive_years: int, report_type: str,
    ) -> set[str]:
        """评估表达式的条件。

        对于简单表达式（单个变量），降级为 metric 条件。
        对于复杂表达式（多变量运算），查询原始数据后在 Python 中计算。
        """
        # 表达式中的变量
        vars_in_expr = _parse_expression(expression)

        if not vars_in_expr:
            raise ValueError(f"表达式中未找到有效指标: {expression}")

        # 表达式可能只有一个变量但用了括号 → 降级为 metric
        if len(vars_in_expr) == 1:
            metric = list(vars_in_expr.values())[0]
            return self._evaluate_metric_condition(
                metric, operator, value, consecutive_years, report_type
            )

        # 多变量表达式 → 先查数据，再在 Python 中计算
        return self._evaluate_complex_expression(
            expression, vars_in_expr, operator, value,
            consecutive_years, report_type,
        )

    def _evaluate_complex_expression(
        self, expr_str: str, vars_in_expr: dict,
        operator: str, value: float,
        consecutive_years: int, report_type: str,
    ) -> set[str]:
        """处理多变量表达式：查数据 → Python 计算 → 筛选。"""
        # 确定需要的字段在各张表上
        fs_fields = []
        ind_fields = []
        for field_name in vars_in_expr.values():
            if field_name in INDICATOR_FIELDS:
                ind_fields.append(field_name)
            else:
                fs_fields.append(field_name)

        # 查所有股票的最近 N 条报表
        from datetime import datetime as dt
        current_year = dt.now().year

        stmts = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.report_type == report_type,
                FinancialStatement.fiscal_year >= current_year - consecutive_years - 1,
            )
            .order_by(FinancialStatement.symbol, FinancialStatement.report_date.desc())
            .all()
        )

        # 按股票分组，每组取最近 consecutive_years 条
        from collections import defaultdict
        stock_stmt_groups = defaultdict(list)
        for s in stmts:
            if len(stock_stmt_groups[s.symbol]) < consecutive_years:
                stock_stmt_groups[s.symbol].append(s)

        # 同样查 indicator
        inds = (
            self.db.query(FinancialIndicator)
            .filter(
                FinancialIndicator.report_type == report_type,
                FinancialIndicator.fiscal_year >= current_year - consecutive_years - 1,
            )
            .order_by(FinancialIndicator.symbol, FinancialIndicator.report_date.desc())
            .all()
        )
        stock_ind_groups = defaultdict(list)
        for ind in inds:
            if len(stock_ind_groups[ind.symbol]) < consecutive_years:
                stock_ind_groups[ind.symbol].append(ind)

        op_fn = self.OP_MAP.get(operator)

        matched = set()
        for symbol, group in stock_stmt_groups.items():
            if len(group) < consecutive_years:
                continue

            all_pass = True
            for i in range(consecutive_years):
                stmt = group[i]
                ind_obj = (
                    stock_ind_groups[symbol][i]
                    if i < len(stock_ind_groups.get(symbol, []))
                    else None
                )

                # 构建变量值字典
                var_vals = {}
                for var_name in vars_in_expr.values():
                    if var_name in INDICATOR_FIELDS:
                        var_vals[var_name] = (
                            float(getattr(ind_obj, var_name))
                            if ind_obj and getattr(ind_obj, var_name) is not None
                            else None
                        )
                    else:
                        var_vals[var_name] = (
                            float(getattr(stmt, var_name))
                            if hasattr(stmt, var_name) and getattr(stmt, var_name) is not None
                            else None
                        )

                # 检查是否有 None 值
                if any(v is None for v in var_vals.values()):
                    all_pass = False
                    break

                # 在 Python 中计算表达式
                try:
                    # 安全的 eval: 将变量替换为数值
                    eval_expr = expr_str
                    for var_name, var_val in var_vals.items():
                        # 使用正则替换单词边界
                        eval_expr = re.sub(
                            r'\b' + re.escape(var_name) + r'\b',
                            str(var_val),
                            eval_expr,
                            flags=re.IGNORECASE,
                        )
                    result = eval(eval_expr, {"__builtins__": {}}, {})
                    if not op_fn(result, value):
                        all_pass = False
                        break
                except Exception:
                    all_pass = False
                    break

            if all_pass:
                matched.add(symbol)

        return matched
