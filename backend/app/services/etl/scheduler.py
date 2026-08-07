"""
ETL 编排器。

协调 fetcher → cleaner → loader 三个环节，
支持全量同步和增量同步两种模式。
"""

import logging
from datetime import datetime, date
from typing import Optional

import pandas as pd

from app.core.database import SessionLocal
from app.models.sync import SyncLog
from app.services.etl.fetcher import DataFetcher
from app.services.etl.cleaner import DataCleaner
from app.services.etl.loader import DataLoader

logger = logging.getLogger(__name__)


class ETLOrchestrator:
    """ETL 编排器。

    协调全流程：
        全量同步：股票列表 → 逐只抓取 → 清洗 → 合并 → 入库 → 计算指标
        增量同步：对比最新报表日期 → 仅抓取新数据

    用法：
        orchestrator = ETLOrchestrator()
        orchestrator.sync_all_stocks(years=5)
    """

    def __init__(self):
        self.fetcher = DataFetcher()
        self.cleaner = DataCleaner()

    # ═══════════════════════════════════════════════════════════
    # 全量同步
    # ═══════════════════════════════════════════════════════════
    def sync_all_stocks(
        self,
        years: int = 5,
        symbols: Optional[list[str]] = None,
        report_types: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> SyncLog:
        """全量同步：获取股票列表 → 逐只抓取最近 N 年数据。

        Args:
            years: 抓取年数
            symbols: 指定股票列表，None 表示全 A 股
            report_types: 指定报表类型，None 表示全部
            dry_run: 仅抓取不写入
        """
        db = SessionLocal()
        loader = DataLoader(db)

        # 创建日志
        sync_log = SyncLog(
            job_type="full_sync",
            status="running",
            stocks_total=0,
            stocks_synced=0,
            stocks_failed=0,
            reports_fetched=0,
            started_at=datetime.now(),
        )
        db.add(sync_log)
        db.commit()
        log_id = sync_log.id

        try:
            # 步骤 1: 获取股票列表
            logger.info("正在获取股票列表...")
            stock_df = self.fetcher.fetch_stock_list()

            if symbols:
                # 过滤指定股票
                stock_df = stock_df[stock_df["symbol"].astype(str).isin(symbols)]

            if len(stock_df) == 0:
                raise ValueError("股票列表为空")

            sync_log.stocks_total = len(stock_df)
            db.commit()

            logger.info(f"共 {len(stock_df)} 只股票待同步")

            # 步骤 1.5: 先写入股票基本信息
            loader.upsert_stocks(stock_df)
                # 获取并写入行业分类
                try:
                    logger.info("正在获取行业分类...")
                    industry_df = self.fetcher.fetch_industry_map()
                    if industry_df is not None and len(industry_df) > 0:
                        loader.upsert_industries(industry_df)
                        logger.info(f"行业分类更新完成: {len(industry_df)} 条")
                except Exception as e:
                    logger.warning(f"行业分类获取失败（不影响主流程）: {e}")

            # 步骤 2: 逐只股票处理
            for i, (_, row) in enumerate(stock_df.iterrows()):
                symbol = str(row["symbol"]).strip()
                name = str(row.get("name", "")).strip()

                try:
                    logger.info(f"[{i+1}/{len(stock_df)}] 正在处理: {symbol} {name}")

                    # 抓取三张报表
                    data = self.fetcher.fetch_all_for_stock(symbol)

                    # 清洗
                    bs_clean = self.cleaner.clean_balance_sheet(
                        data.get("balance_sheet"), symbol
                    )
                    income_clean = self.cleaner.clean_income_statement(
                        data.get("income_statement"), symbol
                    )
                    cf_clean = self.cleaner.clean_cash_flow(
                        data.get("cash_flow"), symbol
                    )

                    # 过滤年数
                    bs_clean = self._filter_years(bs_clean, years)
                    income_clean = self._filter_years(income_clean, years)
                    cf_clean = self._filter_years(cf_clean, years)

                    # 过滤报表类型
                    if report_types:
                        bs_clean = bs_clean[bs_clean["report_type"].isin(report_types)]
                        income_clean = income_clean[income_clean["report_type"].isin(report_types)]
                        cf_clean = cf_clean[cf_clean["report_type"].isin(report_types)]

                    # 合并三张表
                    merged = self.cleaner.merge_statements(
                        bs_clean, income_clean, cf_clean, symbol
                    )

                    if not dry_run:
                        # 入库
                        count = loader.upsert_financials(merged)
                        sync_log.reports_fetched = (sync_log.reports_fetched or 0) + count

                        # 计算指标（仅对年报，因为需要用年均值）
                        loader.compute_and_store_indicators(symbol)

                    sync_log.stocks_synced = (sync_log.stocks_synced or 0) + 1

                except Exception as e:
                    logger.error(f"{symbol} 处理失败: {e}", exc_info=True)
                    sync_log.stocks_failed = (sync_log.stocks_failed or 0) + 1

                # 每 50 只提交一次进度
                if (i + 1) % 50 == 0:
                    db.commit()
                    logger.info(
                        f"进度: {i+1}/{len(stock_df)} "
                        f"(成功: {sync_log.stocks_synced or 0}, "
                        f"失败: {sync_log.stocks_failed or 0})"
                    )

            # 确定最终状态
            if sync_log.stocks_synced == 0:
                sync_log.status = "failed"
            elif sync_log.stocks_failed and sync_log.stocks_failed > 0:
                sync_log.status = "partial"
            else:
                sync_log.status = "success"

        except Exception as e:
            logger.error(f"全量同步异常: {e}", exc_info=True)
            sync_log.status = "failed"
            sync_log.error_details = str(e)

        finally:
            sync_log.completed_at = datetime.now()
            db.commit()

            logger.info(
                f"全量同步完成: "
                f"总计 {sync_log.stocks_total} 只, "
                f"成功 {sync_log.stocks_synced or 0} 只, "
                f"失败 {sync_log.stocks_failed or 0} 只, "
                f"报表 {sync_log.reports_fetched or 0} 行, "
                f"状态: {sync_log.status}"
            )

            loader.close()
            db.close()

        return sync_log

    # ═══════════════════════════════════════════════════════════
    # 全量分批同步
    # ═══════════════════════════════════════════════════════════
    def sync_all_stocks_batch(
        self,
        years: int = 5,
        batch_size: int = 50,
        start_from: int = 0,
    ) -> SyncLog:
        """全量分批同步：自动获取全 A 股列表，分批抓取。

        Args:
            years: 抓取年数
            batch_size: 每批股票数
            start_from: 从第几只开始（断点续传）
        """
        db = SessionLocal()
        loader = DataLoader(db)

        sync_log = SyncLog(
            job_type="full_sync_batch",
            status="running",
            stocks_total=0,
            stocks_synced=0,
            stocks_failed=0,
            reports_fetched=0,
            started_at=datetime.now(),
        )
        db.add(sync_log)
        db.commit()
        log_id = sync_log.id

        try:
            logger.info("正在获取股票列表...")
            stock_df = self.fetcher.fetch_stock_list()
            logger.info(f"全 A 股共 {len(stock_df)} 只")

            loader.upsert_stocks(stock_df)

            sync_log.stocks_total = len(stock_df)
            db.commit()

            # 分批处理
            total = len(stock_df)
            for batch_start in range(start_from, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = stock_df.iloc[batch_start:batch_end]
                logger.info(f"=== 批次 {batch_start//batch_size + 1}: "
                           f"第 {batch_start+1}-{batch_end} 只 / 共 {total} 只 ===")

                for _, row in batch.iterrows():
                    symbol = str(row["symbol"]).strip()
                    try:
                        self._sync_one_stock(symbol, years, loader, sync_log)
                    except Exception as e:
                        logger.error(f"{symbol} 处理失败: {e}")
                        sync_log.stocks_failed = (sync_log.stocks_failed or 0) + 1

                # 每批提交一次
                db.commit()
                logger.info(
                    f"批次完成，累计: 成功 {sync_log.stocks_synced or 0}, "
                    f"失败 {sync_log.stocks_failed or 0}, "
                    f"进度: {batch_end}/{total} ({batch_end*100//total}%)"
                )

            sync_log.status = "success" if (sync_log.stocks_failed or 0) == 0 else "partial"

        except Exception as e:
            logger.error(f"分批同步异常: {e}", exc_info=True)
            sync_log.status = "failed"
            sync_log.error_details = str(e)

        finally:
            sync_log.completed_at = datetime.now()
            db.commit()
            loader.close()
            db.close()

        return sync_log

    def _sync_one_stock(self, symbol, years, loader, sync_log):
        """同步单只股票。"""
        data = self.fetcher.fetch_all_for_stock(symbol)
        bs_clean = self.cleaner.clean_balance_sheet(data.get("balance_sheet"), symbol)
        inc_clean = self.cleaner.clean_income_statement(data.get("income_statement"), symbol)
        cf_clean = self.cleaner.clean_cash_flow(data.get("cash_flow"), symbol)

        bs_clean = self._filter_years(bs_clean, years)
        inc_clean = self._filter_years(inc_clean, years)
        cf_clean = self._filter_years(cf_clean, years)

        merged = self.cleaner.merge_statements(bs_clean, inc_clean, cf_clean, symbol)

        count = loader.upsert_financials(merged)
        sync_log.reports_fetched = (sync_log.reports_fetched or 0) + count
        loader.compute_and_store_indicators(symbol)
        sync_log.stocks_synced = (sync_log.stocks_synced or 0) + 1

    # ═══════════════════════════════════════════════════════════
    # 增量同步（季度更新用）
    # ═══════════════════════════════════════════════════════════
    def incremental_sync(self) -> SyncLog:
        """增量同步：仅更新有新报表的股票。

        对比每只股票的 MAX(report_date) 与当前日期，
        如果最新季报出来后还没同步，则抓取更新。
        适用场景：每季度财报披露后触发一次。
        """
        db = SessionLocal()
        loader = DataLoader(db)

        sync_log = SyncLog(
            job_type="incremental_sync",
            status="running",
            stocks_total=0,
            stocks_synced=0,
            stocks_failed=0,
            reports_fetched=0,
            started_at=datetime.now(),
        )
        db.add(sync_log)
        db.commit()

        try:
            # 获取最新披露窗口
            from app.models.financials import FinancialStatement
            from sqlalchemy import func as sql_func

            today = datetime.now().date()
            current_year = today.year

            # 确定当前应已披露的最新报表期
            if today >= date(current_year, 5, 1):
                latest_period = date(current_year, 3, 31)  # Q1
            elif today >= date(current_year - 1, 5, 1):
                latest_period = date(current_year - 1, 12, 31)  # 上年度年报
            else:
                latest_period = date(current_year - 1, 9, 30)  # 上年度 Q3

            # 查询哪些股票还没有最新报表
            from app.models.stocks import Stock
            stocks = db.query(Stock.symbol).all()
            symbol_list = [s[0] for s in stocks]
            sync_log.stocks_total = len(symbol_list)

            logger.info(f"增量同步: {len(symbol_list)} 只股票，目标报表期 ≥ {latest_period}")

            for symbol in symbol_list:
                latest = (
                    db.query(FinancialStatement)
                    .filter(FinancialStatement.symbol == symbol)
                    .order_by(FinancialStatement.report_date.desc())
                    .first()
                )

                # 已有最新报表则跳过
                if latest and latest.report_date >= latest_period:
                    sync_log.stocks_synced = (sync_log.stocks_synced or 0) + 1
                    continue

                # 需要更新
                try:
                    self._sync_one_stock(symbol, 1, loader, sync_log)
                except Exception as e:
                    logger.error(f"{symbol} 增量更新失败: {e}")
                    sync_log.stocks_failed = (sync_log.stocks_failed or 0) + 1

                if (sync_log.stocks_synced or 0) % 100 == 0:
                    db.commit()

            sync_log.status = "success" if (sync_log.stocks_failed or 0) == 0 else "partial"

        except Exception as e:
            logger.error(f"增量同步异常: {e}", exc_info=True)
            sync_log.status = "failed"
            sync_log.error_details = str(e)

        finally:
            sync_log.completed_at = datetime.now()
            db.commit()
            loader.close()
            db.close()

        return sync_log

    # ── 辅助方法 ──────────────────────────────────────────
    @staticmethod
    def _filter_years(df: pd.DataFrame, years: int) -> pd.DataFrame:
        """仅保留最近 N 个财年的数据。"""
        if df is None or len(df) == 0:
            return df
        if "fiscal_year" not in df.columns:
            return df
        current_year = datetime.now().year
        min_year = current_year - years + 1
        return df[df["fiscal_year"] >= min_year]
