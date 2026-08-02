"""
ETL 同步日志与财报披露日历 ORM 模型。
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Boolean, Text,
    UniqueConstraint,
)

from app.core.database import Base


class SyncLog(Base):
    """ETL 数据同步审计日志。

    每次数据同步任务创建一条记录，记录起止时间、同步数量和状态。
    """

    __tablename__ = "sync_log"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    job_type = Column(
        String(50),
        nullable=False,
        comment="任务类型：full_sync / incremental_sync / metadata_refresh",
    )
    status = Column(
        String(20),
        nullable=False,
        default="running",
        comment="状态：running / success / failed / partial",
    )
    stocks_total = Column(
        Integer,
        comment="待同步股票总数",
    )
    stocks_synced = Column(
        Integer,
        comment="成功同步数",
    )
    stocks_failed = Column(
        Integer,
        comment="失败数",
    )
    reports_fetched = Column(
        Integer,
        comment="抓取到的报表行数",
    )
    error_details = Column(
        Text,
        comment="错误详情（JSON 格式）",
    )
    started_at = Column(
        DateTime,
        nullable=False,
        comment="任务开始时间",
    )
    completed_at = Column(
        DateTime,
        comment="任务完成时间",
    )

    def __repr__(self):
        return f"<SyncLog(id={self.id}, type='{self.job_type}', status='{self.status}')>"


class ReportingCalendar(Base):
    """财报披露日历表。

    记录 A 股各报表期的法定披露截止日，用于规划 ETL 同步时间。
    """

    __tablename__ = "reporting_calendar"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    fiscal_year = Column(
        Integer,
        nullable=False,
        comment="会计年度",
    )
    report_type = Column(
        String(20),
        nullable=False,
        comment="报表类型：annual / semi_annual / q1 / q3",
    )
    deadline_date = Column(
        Date,
        nullable=False,
        comment="法定披露截止日",
    )
    expected_start = Column(
        Date,
        nullable=False,
        comment="数据预计开始出现的时间",
    )
    is_released = Column(
        Boolean,
        default=False,
        comment="该披露窗口是否已过",
    )

    __table_args__ = (
        UniqueConstraint(
            "fiscal_year", "report_type",
            name="uq_calendar_year_type",
        ),
    )

    def __repr__(self):
        return (
            f"<ReportingCalendar("
            f"FY{self.fiscal_year} {self.report_type}, "
            f"deadline={self.deadline_date})>"
        )
