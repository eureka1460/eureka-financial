"""
akshare 列名 → 数据库字段名映射表。

akshare 东方财富接口 (stock_*_by_report_em) 返回的 DataFrame
列名为英文缩写（如 TOTAL_ASSETS、OPERATE_INCOME），
需要统一映射到 financial_statements 表的字段名。

注意：akshare 还会为每个指标生成 _YOY 后缀列（同比增速），
这些列不需要映射，ETL 阶段会自行计算增长率。
"""

# ═══════════════════════════════════════════════════════════════
# 资产负债表列名映射（东方财富）
# ═══════════════════════════════════════════════════════════════
BALANCE_SHEET_MAPPING = {
    # ── 元数据 ──
    "REPORT_DATE": "report_date",
    "REPORT_TYPE": "report_type",
    # ── 资产 ──
    "TOTAL_ASSETS": "total_assets",
    "TOTAL_CURRENT_ASSETS": "current_assets",
    "MONETARYFUNDS": "cash_and_equivalents",  # 货币资金
    "TRADE_FINASSET_NOTFVTPL": "trading_financial_assets",  # 交易性金融资产
    "FVTPL_FINASSET": "trading_financial_assets",  # 以公允价值计量的金融资产
    "NOTES_RECEIV": "notes_receivable",  # 应收票据
    "ACCOUNTS_RECEIVABLE": "accounts_receivable",  # 应收账款
    "ADVANCE_PAYMENT": "prepayments",  # 预付款项
    "PREPAYMENT": "prepayments",
    "OTHER_RECEIVABLES": "other_receivables",  # 其他应收款
    "INVENTORY": "inventory",  # 存货
    "INVENTORIES": "inventory",
    "TOTAL_NONCURRENT_ASSETS": "non_current_assets",
    "FIXED_ASSET": "fixed_assets",  # 固定资产
    "CONSTRUCT_IN_PROGRESS": "construction_in_progress",  # 在建工程
    "INTANGIBLE_ASSET": "intangible_assets",  # 无形资产
    "GOODWILL": "goodwill",  # 商誉
    "LONG_EQUITY_INVEST": "long_term_equity_investments",  # 长期股权投资
    "DEFER_TAX_ASSET": "deferred_tax_assets",  # 递延所得税资产
    # ── 负债 ──
    "TOTAL_LIABILITIES": "total_liabilities",
    "TOTAL_CURRENT_LIAB": "current_liabilities",
    "TOTAL_CURRENT_LIABILITIES": "current_liabilities",
    "SHORTTERM_BORROW": "short_term_borrowings",  # 短期借款
    "NOTES_PAYABLE": "notes_payable",  # 应付票据
    "ACCOUNTS_PAYABLE": "accounts_payable",  # 应付账款
    "CONTRACT_LIAB": "contract_liabilities",  # 合同负债
    "ADVANCE_RECEIPTS": "contract_liabilities",
    "EMPLOYEE_PAY": "employee_payable",  # 应付职工薪酬
    "TAX_PAYABLE": "taxes_payable",  # 应交税费
    "TOTAL_NONCURRENT_LIAB": "non_current_liabilities",
    "LONGTERM_BORROW": "long_term_borrowings",  # 长期借款
    "BOND_PAYABLE": "bonds_payable",  # 应付债券
    "DEFER_TAX_LIAB": "deferred_tax_liabilities",  # 递延所得税负债
    # ── 权益 ──
    "TOTAL_EQUITY": "total_equity",
    "SHARE_CAPITAL": "paid_in_capital",  # 实收资本/股本
    "CAPITAL_RESERVE": "capital_reserve",  # 资本公积
    "SURPLUS_RESERVE": "surplus_reserve",  # 盈余公积
    "RETAINED_EARNING": "retained_earnings",  # 未分配利润
    "MINORITY_EQUITY": "minority_interest",  # 少数股东权益
}

# ═══════════════════════════════════════════════════════════════
# 利润表列名映射（东方财富）
# ═══════════════════════════════════════════════════════════════
INCOME_STATEMENT_MAPPING = {
    # ── 元数据 ──
    "REPORT_DATE": "report_date",
    "REPORT_TYPE": "report_type",
    # ── 收入与成本 ──
    "TOTAL_OPERATE_INCOME": "operating_revenue",  # 营业总收入（顶行收入）★
    "TOTAL_OPERATE_COST": "operating_cost",  # 营业总成本
    # ── 费用 ──
    "SALE_EXPENSE": "selling_expenses",  # 销售费用
    "MANAGE_EXPENSE": "administrative_expenses",  # 管理费用
    "RD_EXPENSE": "r_and_d_expenses",  # 研发费用
    "FINANCE_EXPENSE": "financial_expenses",  # 财务费用（利润表）
    "FE_INTEREST_EXPENSE": "interest_expense",  # 利息费用（明细）
    # ── 其他收支 ──
    "INVEST_INCOME": "investment_income",  # 投资收益
    "FAIRVALUE_CHANGE_INCOME": "fair_value_change",  # 公允价值变动收益
    "ASSET_IMPAIRMENT_INCOME": "asset_impairment_loss",  # 资产减值损失
    "CREDIT_IMPAIRMENT_INCOME": "credit_impairment_loss",  # 信用减值损失
    "OPERATE_TAX_ADD": "taxes_and_surcharges",  # 税金及附加
    # ── 利润 ──
    "OPERATE_PROFIT": "operating_profit",  # 营业利润
    "TOTAL_PROFIT": "total_profit",  # 利润总额
    "INCOME_TAX": "income_tax_expense",  # 所得税费用
    "NETPROFIT": "net_profit",  # 净利润（含少数股东）
    "PARENT_NETPROFIT": "net_profit_attr_parent",  # 归母净利润
    "DEDUCT_PARENT_NETPROFIT": "net_profit_excl_nonrecurring",  # 扣非归母净利润
    "MINORITY_PROFIT": "minority_profit",  # 少数股东损益
    # ── 每股指标 ──
    "BASIC_EPS": "basic_eps",  # 基本每股收益
    "DILUTED_EPS": "diluted_eps",  # 稀释每股收益
    # ── 其他 ──
    "OTHER_COMPRE_INCOME": "other_comprehensive_income",  # 其他综合收益
}

# ═══════════════════════════════════════════════════════════════
# 现金流量表列名映射（东方财富）
# ═══════════════════════════════════════════════════════════════
CASH_FLOW_MAPPING = {
    # ── 元数据 ──
    "REPORT_DATE": "report_date",
    "REPORT_TYPE": "report_type",
    # ── 经营活动 ──
    "NETCASH_OPERATE": "net_operating_cashflow",  # 经营活动现金流净额
    "TOTAL_OPERATE_INFLOW": "cash_from_sales",  # 销售商品提供劳务收到的现金
    "PAY_STAFF_CASH": "cash_paid_to_employees",  # 支付给职工
    "PAY_ALL_TAX": "taxes_paid",  # 支付的各项税费
    # ── 投资活动 ──
    "NETCASH_INVEST": "net_investing_cashflow",  # 投资活动现金流净额
    "INVEST_NETCASH_BALANCE": "net_investing_cashflow",
    "CONSTRUCT_BUY_PAY": "capital_expenditure",  # 构建固定资产支付的现金（= 资本支出）
    # ── 筹资活动 ──
    "NETCASH_FINANCE": "net_financing_cashflow",  # 筹资活动现金流净额
    "FINANCE_NETCASH_BALANCE": "net_financing_cashflow",
    "RECEIVE_LOAN_CASH": "cash_from_borrowings",  # 取得借款收到的现金
    "PAY_DIVIDEND_INTEREST": "dividends_paid",  # 分配股利、偿付利息支付的现金
    "PAY_INTEREST_DIVIDEND": "dividends_paid",
    # ── 净额与余额 ──
    "NETCASH_CHANGE": "net_change_in_cash",  # 现金及等价物净增加额
    "CASH_CHANGE": "net_change_in_cash",
    "BEGIN_CASH": "beginning_cash_balance",  # 期初现金余额
    "BEGIN_CASH_EQUIVALENTS": "beginning_cash_balance",
    "END_CASH": "ending_cash_balance",  # 期末现金余额
    "END_CASH_EQUIVALENTS": "ending_cash_balance",
}

# ═══════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════
ALL_MAPPINGS = {
    "balance_sheet": BALANCE_SHEET_MAPPING,
    "income_statement": INCOME_STATEMENT_MAPPING,
    "cash_flow": CASH_FLOW_MAPPING,
}


def get_mapping(sheet_type: str) -> dict[str, str]:
    """获取指定报表类型的列名映射。

    Args:
        sheet_type: "balance_sheet" | "income_statement" | "cash_flow"

    Returns:
        akshare 英文列名 → 数据库英文字段名的映射字典
    """
    if sheet_type not in ALL_MAPPINGS:
        raise ValueError(f"未知报表类型: {sheet_type}，可选值: {list(ALL_MAPPINGS.keys())}")
    return ALL_MAPPINGS[sheet_type]


def get_all_mapped_columns() -> list[str]:
    """获取所有映射后的数据库字段名。"""
    all_cols = set()
    for mapping in ALL_MAPPINGS.values():
        all_cols.update(mapping.values())
    return sorted(all_cols)
