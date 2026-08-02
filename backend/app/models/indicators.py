"""
计算指标 ORM 模型。

存储在 ETL 过程中自动计算的财务比率和衍生指标。
与 financial_statements 一一对应（同一 symbol + report_date + report_type）。
"""

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric,
    UniqueConstraint, ForeignKey,
)
from sqlalchemy.sql import func

from app.core.database import Base


class FinancialIndicator(Base):
    """财务计算指标表。

    每条记录对应 financial_statements 中的一条原始数据。
    所有比率型指标统一存储为小数形式（如 0.15 表示 15%），
    前端自行转换百分比显示。
    """

    __tablename__ = "financial_indicators"

    # ── 元数据 ──────────────────────────────────────────────
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    symbol = Column(
        String(10),
        ForeignKey("stocks.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    report_date = Column(
        Date,
        nullable=False,
    )
    report_type = Column(
        String(20),
        nullable=False,
    )
    fiscal_year = Column(
        Integer,
        nullable=False,
    )

    # ══════════════════════════════════════════════════════════
    # 盈利能力
    # ══════════════════════════════════════════════════════════
    roe = Column(
        Numeric(12, 6),
        comment="净资产收益率 = 归母净利润 / 平均净资产",
    )
    roa = Column(
        Numeric(12, 6),
        comment="总资产收益率 = 净利润 / 平均总资产",
    )
    gross_margin = Column(
        Numeric(12, 6),
        comment="毛利率 = (营收 - 营业成本) / 营收",
    )
    net_margin = Column(
        Numeric(12, 6),
        comment="净利率 = 归母净利润 / 营收",
    )
    operating_margin = Column(
        Numeric(12, 6),
        comment="营业利润率 = 营业利润 / 营收",
    )

    # ══════════════════════════════════════════════════════════
    # 成长能力（同比增速）
    # ══════════════════════════════════════════════════════════
    revenue_yoy = Column(
        Numeric(12, 6),
        comment="营收同比增长率",
    )
    net_profit_yoy = Column(
        Numeric(12, 6),
        comment="归母净利润同比增长率",
    )
    operating_profit_yoy = Column(
        Numeric(12, 6),
        comment="营业利润同比增长率",
    )
    eps_yoy = Column(
        Numeric(12, 6),
        comment="EPS 同比增长率",
    )

    # ══════════════════════════════════════════════════════════
    # 偿债与流动性
    # ══════════════════════════════════════════════════════════
    current_ratio = Column(
        Numeric(12, 6),
        comment="流动比率 = 流动资产 / 流动负债",
    )
    quick_ratio = Column(
        Numeric(12, 6),
        comment="速动比率 = (货币资金 + 应收类) / 流动负债",
    )
    debt_to_assets = Column(
        Numeric(12, 6),
        comment="资产负债率 = 总负债 / 总资产",
    )
    debt_to_equity = Column(
        Numeric(12, 6),
        comment="权益乘数 = 总负债 / 总权益",
    )
    interest_coverage = Column(
        Numeric(12, 6),
        comment="利息保障倍数 = 营业利润 / 利息费用",
    )

    # ══════════════════════════════════════════════════════════
    # 营运效率
    # ══════════════════════════════════════════════════════════
    asset_turnover = Column(
        Numeric(12, 6),
        comment="总资产周转率 = 营收 / 平均总资产",
    )
    inventory_turnover = Column(
        Numeric(12, 6),
        comment="存货周转率",
    )
    receivable_turnover = Column(
        Numeric(12, 6),
        comment="应收账款周转率",
    )

    # ══════════════════════════════════════════════════════════
    # 估值相关
    # ══════════════════════════════════════════════════════════
    fcf = Column(
        Numeric(28, 2),
        comment="自由现金流 = 经营现金流净额 - 资本支出",
    )
    dividend_per_share = Column(
        Numeric(18, 4),
        comment="每股股利（元）",
    )
    book_value_per_share = Column(
        Numeric(18, 4),
        comment="每股净资产（元）= 总权益 / 总股本",
    )

    # ══════════════════════════════════════════════════════════
    # 单季度值（从累积值推导）
    # ══════════════════════════════════════════════════════════
    revenue_single_q = Column(
        Numeric(28, 2),
        comment="单季度营业收入",
    )
    net_profit_single_q = Column(
        Numeric(28, 2),
        comment="单季度归母净利润",
    )
    operating_cashflow_single_q = Column(
        Numeric(28, 2),
        comment="单季度经营现金流",
    )

    # ── 元数据 ──────────────────────────────────────────────
    created_at = Column(
        DateTime,
        server_default=func.now(),
        comment="记录创建时间",
    )

    # ── 约束 ───────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "symbol", "report_date", "report_type",
            name="uq_indicators_symbol_date_type",
        ),
    )

    def __repr__(self):
        return (
            f"<FinancialIndicator("
            f"symbol='{self.symbol}', "
            f"date={self.report_date}, "
            f"ROE={self.roe})>"
        )
