"""
股票信息 ORM 模型。

每行代表一只 A 股上市公司的基本信息。
"""

from sqlalchemy import Column, String, Boolean, Date, DateTime, Numeric
from sqlalchemy.sql import func

from app.core.database import Base


class Stock(Base):
    """A 股股票基础信息表。"""

    __tablename__ = "stocks"

    # ── 主键 ────────────────────────────────────────────────
    symbol = Column(
        String(10),
        primary_key=True,
        comment="股票代码，如 '600519'",
    )

    # ── 基本信息 ────────────────────────────────────────────
    name = Column(
        String(50),
        nullable=False,
        index=True,
        comment="股票简称，如 '贵州茅台'",
    )
    market = Column(
        String(2),
        nullable=False,
        comment="交易所：SH(上海) / SZ(深圳) / BJ(北交所)",
    )
    industry = Column(
        String(50),
        index=True,
        comment="申万一级行业分类",
    )
    sub_industry = Column(
        String(50),
        comment="申万二级行业分类",
    )
    list_date = Column(
        Date,
        comment="上市日期",
    )
    is_active = Column(
        Boolean,
        default=True,
        comment="是否仍上市（剔除退市股）",
    )
    total_shares = Column(
        Numeric(20, 2),
        comment="总股本（股），用于计算每股指标和估值",
    )

    # ── 元数据 ──────────────────────────────────────────────
    created_at = Column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="最后更新时间",
    )

    def __repr__(self):
        return f"<Stock(symbol='{self.symbol}', name='{self.name}')>"
