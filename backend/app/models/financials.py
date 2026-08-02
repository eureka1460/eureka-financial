"""
财务报表 ORM 模型（核心宽表）。

每行 = 一只股票在一个报表期的一份完整财务报表。
涵盖资产负债表、利润表、现金流量表的全部核心字段。
"""

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric,
    UniqueConstraint, ForeignKey, Index,
)

from sqlalchemy.sql import func

from app.core.database import Base


class FinancialStatement(Base):
    """财务报表宽表。

    来自 akshare 的原始数据，所有金额单位为人民币元。
    利润表和现金流量表数据为年初至今累积值 (YTD)。
    """

    __tablename__ = "financial_statements"

    # ── 元数据 ──────────────────────────────────────────────
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )
    symbol = Column(
        String(10),
        ForeignKey("stocks.symbol", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="股票代码",
    )
    report_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="报表截止日，如 2024-12-31",
    )
    report_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="报表类型：annual / semi_annual / q1 / q3",
    )
    fiscal_year = Column(
        Integer,
        nullable=False,
        index=True,
        comment="会计年度，如 2024",
    )
    currency = Column(
        String(10),
        default="CNY",
        comment="币种",
    )
    data_source = Column(
        String(50),
        default="eastmoney",
        comment="数据来源：eastmoney / sina",
    )

    # ══════════════════════════════════════════════════════════
    # 资产负债表 —— 资产
    # ══════════════════════════════════════════════════════════
    total_assets = Column(Numeric(28, 2), comment="总资产")
    current_assets = Column(Numeric(28, 2), comment="流动资产合计")
    cash_and_equivalents = Column(Numeric(28, 2), comment="货币资金")
    trading_financial_assets = Column(Numeric(28, 2), comment="交易性金融资产")
    notes_receivable = Column(Numeric(28, 2), comment="应收票据")
    accounts_receivable = Column(Numeric(28, 2), comment="应收账款")
    prepayments = Column(Numeric(28, 2), comment="预付款项")
    other_receivables = Column(Numeric(28, 2), comment="其他应收款")
    inventory = Column(Numeric(28, 2), comment="存货")
    non_current_assets = Column(Numeric(28, 2), comment="非流动资产合计")
    fixed_assets = Column(Numeric(28, 2), comment="固定资产")
    construction_in_progress = Column(Numeric(28, 2), comment="在建工程")
    intangible_assets = Column(Numeric(28, 2), comment="无形资产")
    goodwill = Column(Numeric(28, 2), comment="商誉")
    long_term_equity_investments = Column(Numeric(28, 2), comment="长期股权投资")
    deferred_tax_assets = Column(Numeric(28, 2), comment="递延所得税资产")

    # ══════════════════════════════════════════════════════════
    # 资产负债表 —— 负债
    # ══════════════════════════════════════════════════════════
    total_liabilities = Column(Numeric(28, 2), comment="总负债")
    current_liabilities = Column(Numeric(28, 2), comment="流动负债合计")
    short_term_borrowings = Column(Numeric(28, 2), comment="短期借款")
    notes_payable = Column(Numeric(28, 2), comment="应付票据")
    accounts_payable = Column(Numeric(28, 2), comment="应付账款")
    contract_liabilities = Column(Numeric(28, 2), comment="合同负债")
    employee_payable = Column(Numeric(28, 2), comment="应付职工薪酬")
    taxes_payable = Column(Numeric(28, 2), comment="应交税费")
    non_current_liabilities = Column(Numeric(28, 2), comment="非流动负债合计")
    long_term_borrowings = Column(Numeric(28, 2), comment="长期借款")
    bonds_payable = Column(Numeric(28, 2), comment="应付债券")
    deferred_tax_liabilities = Column(Numeric(28, 2), comment="递延所得税负债")

    # ══════════════════════════════════════════════════════════
    # 资产负债表 —— 权益
    # ══════════════════════════════════════════════════════════
    total_equity = Column(Numeric(28, 2), comment="所有者权益合计")
    paid_in_capital = Column(Numeric(28, 2), comment="实收资本（股本）")
    capital_reserve = Column(Numeric(28, 2), comment="资本公积")
    surplus_reserve = Column(Numeric(28, 2), comment="盈余公积")
    retained_earnings = Column(Numeric(28, 2), comment="未分配利润")
    minority_interest = Column(Numeric(28, 2), comment="少数股东权益")

    # ══════════════════════════════════════════════════════════
    # 利润表（年初至今累积值 YTD）
    # ══════════════════════════════════════════════════════════
    operating_revenue = Column(Numeric(28, 2), comment="营业总收入")
    operating_cost = Column(Numeric(28, 2), comment="营业总成本")
    selling_expenses = Column(Numeric(28, 2), comment="销售费用")
    administrative_expenses = Column(Numeric(28, 2), comment="管理费用")
    r_and_d_expenses = Column(Numeric(28, 2), comment="研发费用")
    financial_expenses = Column(Numeric(28, 2), comment="财务费用")
    interest_expense = Column(Numeric(28, 2), comment="利息费用（明细）")
    investment_income = Column(Numeric(28, 2), comment="投资收益")
    fair_value_change = Column(Numeric(28, 2), comment="公允价值变动收益")
    asset_impairment_loss = Column(Numeric(28, 2), comment="资产减值损失")
    credit_impairment_loss = Column(Numeric(28, 2), comment="信用减值损失")
    taxes_and_surcharges = Column(Numeric(28, 2), comment="税金及附加")
    operating_profit = Column(Numeric(28, 2), comment="营业利润")
    total_profit = Column(Numeric(28, 2), comment="利润总额")
    income_tax_expense = Column(Numeric(28, 2), comment="所得税费用")
    net_profit = Column(Numeric(28, 2), comment="净利润（含少数股东）")
    net_profit_attr_parent = Column(Numeric(28, 2), comment="归母净利润")
    net_profit_excl_nonrecurring = Column(Numeric(28, 2), comment="扣非归母净利润")
    minority_profit = Column(Numeric(28, 2), comment="少数股东损益")
    basic_eps = Column(Numeric(18, 4), comment="基本每股收益（元）")
    diluted_eps = Column(Numeric(18, 4), comment="稀释每股收益（元）")
    other_comprehensive_income = Column(Numeric(28, 2), comment="其他综合收益")

    # ══════════════════════════════════════════════════════════
    # 现金流量表（年初至今累积值 YTD）
    # ══════════════════════════════════════════════════════════
    net_operating_cashflow = Column(Numeric(28, 2), comment="经营活动现金流净额")
    cash_from_sales = Column(Numeric(28, 2), comment="销售商品提供劳务收到的现金")
    cash_paid_to_employees = Column(Numeric(28, 2), comment="支付给职工及为职工支付的现金")
    taxes_paid = Column(Numeric(28, 2), comment="支付的各项税费")
    net_investing_cashflow = Column(Numeric(28, 2), comment="投资活动现金流净额")
    capital_expenditure = Column(Numeric(28, 2), comment="购建固定资产无形资产支付的现金（资本支出）")
    net_financing_cashflow = Column(Numeric(28, 2), comment="筹资活动现金流净额")
    cash_from_borrowings = Column(Numeric(28, 2), comment="取得借款收到的现金")
    dividends_paid = Column(Numeric(28, 2), comment="分配股利、偿付利息支付的现金")
    net_change_in_cash = Column(Numeric(28, 2), comment="现金及现金等价物净增加额")
    beginning_cash_balance = Column(Numeric(28, 2), comment="期初现金及现金等价物余额")
    ending_cash_balance = Column(Numeric(28, 2), comment="期末现金及现金等价物余额")

    # ── 元数据 ──────────────────────────────────────────────
    created_at = Column(
        DateTime,
        server_default=func.now(),
        comment="记录创建时间",
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="记录更新时间",
    )

    # ── 约束与索引 ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "symbol", "report_date", "report_type",
            name="uq_financials_symbol_date_type",
        ),
        Index("idx_fs_symbol", "symbol"),
        Index("idx_fs_report_date", "report_date"),
        Index("idx_fs_fiscal_year", "fiscal_year"),
        Index("idx_fs_report_type", "report_type"),
    )

    def __repr__(self):
        return (
            f"<FinancialStatement("
            f"symbol='{self.symbol}', "
            f"date={self.report_date}, "
            f"type='{self.report_type}')>"
        )
