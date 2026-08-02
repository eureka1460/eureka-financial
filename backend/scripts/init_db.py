"""
数据库初始化脚本。

用法：
    python scripts/init_db.py          # 创建所有表
    python scripts/init_db.py --drop   # 删除后重建
    python scripts/init_db.py --seed   # 创建表 + 预置财报日历数据
"""

import sys
import os
from datetime import date
from argparse import ArgumentParser

# 确保 backend/ 在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
# 导入所有模型，确保 Base.metadata 注册
from app.models import Stock, FinancialStatement, FinancialIndicator, SyncLog, ReportingCalendar  # noqa: F401
from app.models.sync import ReportingCalendar


def create_tables():
    """创建所有表。"""
    Base.metadata.create_all(bind=engine)
    print("所有表创建完成。")
    list_tables()


def drop_tables():
    """删除所有表（谨慎使用）。"""
    confirm = input("确认删除所有表？这将丢失所有数据！输入 yes 继续: ")
    if confirm.lower() == "yes":
        Base.metadata.drop_all(bind=engine)
        print("所有表已删除。")
    else:
        print("操作已取消。")


def list_tables():
    """列出当前数据库中的表。"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n当前数据库表 ({len(tables)} 张)：")
    for t in tables:
        columns = [c["name"] for c in inspector.get_columns(t)]
        print(f"  [{len(columns)} cols] {t}")
        # 只显示前 5 列名，避免输出过长
        col_preview = columns[:5]
        if len(columns) > 5:
            col_preview.append(f"... 等 {len(columns)} 列")
        print(f"     {', '.join(col_preview)}")


def seed_calendar():
    """预置 A 股财报披露日历（2024-2026）。"""
    db = SessionLocal()
    try:
        calendar_data = [
            # (fiscal_year, report_type, deadline_date, expected_start)
            (2024, "annual",       date(2025, 4, 30),  date(2025, 3, 1)),
            (2024, "q1",           date(2025, 4, 30),  date(2025, 4, 1)),
            (2024, "semi_annual",  date(2024, 8, 31),  date(2024, 8, 1)),
            (2024, "q3",           date(2024, 10, 31), date(2024, 10, 1)),
            (2025, "annual",       date(2026, 4, 30),  date(2026, 3, 1)),
            (2025, "q1",           date(2026, 4, 30),  date(2026, 4, 1)),
            (2025, "semi_annual",  date(2025, 8, 31),  date(2025, 8, 1)),
            (2025, "q3",           date(2025, 10, 31), date(2025, 10, 1)),
            (2026, "annual",       date(2027, 4, 30),  date(2027, 3, 1)),
            (2026, "q1",           date(2027, 4, 30),  date(2027, 4, 1)),
            (2026, "semi_annual",  date(2026, 8, 31),  date(2026, 8, 1)),
            (2026, "q3",           date(2026, 10, 31), date(2026, 10, 1)),
        ]

        count = 0
        for fy, rt, dd, es in calendar_data:
            existing = (
                db.query(ReportingCalendar)
                .filter_by(fiscal_year=fy, report_type=rt)
                .first()
            )
            if not existing:
                db.add(ReportingCalendar(
                    fiscal_year=fy,
                    report_type=rt,
                    deadline_date=dd,
                    expected_start=es,
                    is_released=(date.today() > dd),
                ))
                count += 1

        db.commit()
        print(f"财报日历预置完成：新增 {count} 条记录。")
    finally:
        db.close()


if __name__ == "__main__":
    parser = ArgumentParser(description="数据库初始化工具")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除所有表后重建",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="预置财报披露日历数据",
    )
    args = parser.parse_args()

    print(f"数据库位置: {settings.DATABASE_URL}")

    if args.drop:
        drop_tables()

    create_tables()

    if args.seed or args.drop:
        seed_calendar()

    print("\n初始化完成。")
