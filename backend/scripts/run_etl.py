"""
ETL 手动触发脚本。

用法：
    python scripts/run_etl.py                              # 全量同步，全 A 股，5 年
    python scripts/run_etl.py --symbols 600519,000858       # 仅同步指定股票
    python scripts/run_etl.py --years 3                     # 仅拉取最近 3 年
    python scripts/run_etl.py --symbols 600519 --dry-run   # 仅抓取不写入（调试用）
    python scripts/run_etl.py --sync-type incremental       # 增量同步

注意：
    - 全量同步 5000 只股票预计耗时 4~8 小时（受限于 akshare 限速）
    - 建议先用 --symbols 指定少量股票测试
"""

import sys
import os
import logging
from argparse import ArgumentParser

# 确保 backend/ 在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.etl.scheduler import ETLOrchestrator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    parser = ArgumentParser(description="A 股财报数据 ETL 工具")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="指定股票代码，逗号分隔（如 600519,000858）。不传则全量。",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="抓取最近几年的数据（默认 5 年）",
    )
    parser.add_argument(
        "--sync-type",
        type=str,
        default="full",
        choices=["full", "incremental"],
        help="同步类型：full(全量) / incremental(增量)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅抓取不写入数据库（调试用）",
    )
    parser.add_argument(
        "--report-types",
        type=str,
        default=None,
        help="报表类型，逗号分隔（如 annual,q1）。不传则全部。",
    )
    args = parser.parse_args()

    # 解析参数
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]

    report_types = None
    if args.report_types:
        report_types = [r.strip() for r in args.report_types.split(",")]

    # 提示
    if symbols:
        print(f"即将同步 {len(symbols)} 只股票: {', '.join(symbols)}")
    else:
        print("即将同步全 A 股（约 5000 只），预计耗时 4~8 小时。")
        print("建议先用 --symbols 指定少量股票测试。")
        confirm = input("确认继续？(y/N): ")
        if confirm.lower() not in ("y", "yes"):
            print("已取消。")
            return

    print(f"参数: years={args.years}, sync_type={args.sync_type}, "
          f"dry_run={args.dry_run}, report_types={report_types}")
    print("开始执行...\n")

    # 执行
    orchestrator = ETLOrchestrator()

    if args.sync_type == "full":
        result = orchestrator.sync_all_stocks(
            years=args.years,
            symbols=symbols,
            report_types=report_types,
            dry_run=args.dry_run,
        )
    else:
        result = orchestrator.incremental_sync()

    # 输出结果
    print(f"\n{'='*50}")
    print(f"同步完成!")
    print(f"  状态: {result.status}")
    print(f"  股票总数: {result.stocks_total}")
    print(f"  成功: {result.stocks_synced}")
    print(f"  失败: {result.stocks_failed}")
    print(f"  报表行数: {result.reports_fetched}")
    if result.error_details:
        print(f"  错误: {result.error_details[:200]}")

    if result.status == "failed":
        print("\n所有股票均同步失败，请检查：")
        print("  1. 网络是否正常")
        print("  2. akshare 版本是否为最新: pip install --upgrade akshare")
        print("  3. 股票代码是否正确")


if __name__ == "__main__":
    main()
