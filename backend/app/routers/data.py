"""
数据同步管理 API 路由。

提供手动触发 ETL 同步、查询同步状态和测试数据注入。
"""

import threading
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.stocks import Stock
from app.models.financials import FinancialStatement
from app.models.indicators import FinancialIndicator
from app.models.sync import SyncLog
from app.schemas.common import APIResponse
from app.schemas.financials import SyncRequest
from app.services.etl.scheduler import ETLOrchestrator

router = APIRouter(prefix="/api/v1", tags=["data"])


# ═══════════════════════════════════════════════════════════════
# 触发数据同步
# ═══════════════════════════════════════════════════════════════
@router.post("/data/sync", response_model=APIResponse[dict])
def trigger_sync(
    request: SyncRequest,
    db: Session = Depends(get_db),
):
    """触发 ETL 数据同步任务（后台执行）。

    同步在后台线程中异步执行，立即返回 job_id 用于查询进度。
    """
    # 后台线程执行同步
    def _run_sync():
        orchestrator = ETLOrchestrator()
        if request.sync_type == "full_sync":
            orchestrator.sync_all_stocks(
                years=request.years,
                symbols=request.symbols,
                report_types=request.report_types,
            )
        else:
            orchestrator.incremental_sync()

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()

    return APIResponse(
        message=f"同步任务已启动（{request.sync_type}）",
        data={"status": "started"},
    )


# ═══════════════════════════════════════════════════════════════
# 查询同步状态
# ═══════════════════════════════════════════════════════════════
@router.get("/data/sync/status", response_model=APIResponse[list[dict]])
def get_sync_status(db: Session = Depends(get_db)):
    """查询最近 10 条同步任务的执行状态。"""
    jobs = (
        db.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .limit(10)
        .all()
    )

    results = []
    for j in jobs:
        results.append({
            "id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "stocks_total": j.stocks_total,
            "stocks_synced": j.stocks_synced,
            "stocks_failed": j.stocks_failed,
            "reports_fetched": j.reports_fetched,
            "error_details": j.error_details,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        })

    return APIResponse(data=results)


# ═══════════════════════════════════════════════════════════════
# 注入测试数据
# ═══════════════════════════════════════════════════════════════
@router.post("/data/seed-mock", response_model=APIResponse[dict])
def seed_mock_data(db: Session = Depends(get_db)):
    """注入 3 只虚构股票及完整财务数据，用于功能测试。"""

    # ── 虚构股票定义 ──
    mock_stocks = [
        {
            "symbol": "100001", "name": "猴子科技", "market": "SZ",
            "industry": "电子", "sub_industry": "消费电子",
            "list_date": date(2020, 6, 15), "total_shares": 2_500_000_000,
        },
        {
            "symbol": "200002", "name": "猪模块", "market": "SH",
            "industry": "计算机", "sub_industry": "软件开发",
            "list_date": date(2018, 3, 22), "total_shares": 1_800_000_000,
        },
        {
            "symbol": "300003", "name": "太空探索技术", "market": "BJ",
            "industry": "国防军工", "sub_industry": "航天装备",
            "list_date": date(2022, 11, 8), "total_shares": 3_200_000_000,
        },
    ]

    # ── 构建 3 年 × 4 季度 财务数据 ──
    # 格式: (symbol, fiscal_year, 季度 multiplier)
    # 营收/利润/资产 逐年增长，体现不同公司特征
    company_configs = {
        "100001": {  # 猴子科技 — 高增长电子股
            "rev_base": 80_000_000_000, "rev_growth": 0.25,
            "profit_margin": 0.12, "asset_base": 120_000_000_000,
            "equity_ratio": 0.55, "borrowing_ratio": 0.15,
            "cash_ratio": 0.20, "inventory_ratio": 0.18,
            "rd_ratio": 0.08, "capex_ratio": 0.10,
            "dividend_payout": 0.20,
        },
        "200002": {  # 猪模块 — 稳健软件股
            "rev_base": 15_000_000_000, "rev_growth": 0.15,
            "profit_margin": 0.22, "asset_base": 30_000_000_000,
            "equity_ratio": 0.70, "borrowing_ratio": 0.05,
            "cash_ratio": 0.35, "inventory_ratio": 0.02,
            "rd_ratio": 0.18, "capex_ratio": 0.05,
            "dividend_payout": 0.30,
        },
        "300003": {  # 太空探索技术 — 重资产军工股
            "rev_base": 50_000_000_000, "rev_growth": 0.35,
            "profit_margin": 0.08, "asset_base": 200_000_000_000,
            "equity_ratio": 0.40, "borrowing_ratio": 0.35,
            "cash_ratio": 0.10, "inventory_ratio": 0.25,
            "rd_ratio": 0.15, "capex_ratio": 0.20,
            "dividend_payout": 0.10,
        },
    }

    years = [2024, 2025, 2026]
    quarters = [
        ("03-31", "q1"),
        ("06-30", "semi_annual"),
        ("09-30", "q3"),
        ("12-31", "annual"),
    ]

    stocks_created = 0
    stmts_created = 0
    inds_created = 0

    # 先创建股票（需要 commit 后才能关联外键）
    for stock_info in mock_stocks:
        existing = db.query(Stock).filter(Stock.symbol == stock_info["symbol"]).first()
        if not existing:
            db.add(Stock(**stock_info))
            stocks_created += 1
    db.commit()

    for stock_info in mock_stocks:
        symbol = stock_info["symbol"]
        cfg = company_configs[symbol]

        for fy in years:
            fy_offset = fy - 2024  # 0, 1, 2
            growth = (1 + cfg["rev_growth"]) ** fy_offset

            # 全年汇总值
            annual_rev = cfg["rev_base"] * growth
            annual_op_cost = annual_rev * (1 - cfg["profit_margin"] - 0.15)
            annual_op_profit = annual_rev * (cfg["profit_margin"] + 0.05)
            annual_net_profit = annual_rev * cfg["profit_margin"]
            annual_net_profit_attr = annual_net_profit * 0.92
            annual_ocf = annual_net_profit * 1.3
            annual_capex = annual_rev * cfg["capex_ratio"]
            annual_dividends = annual_net_profit_attr * cfg["dividend_payout"]

            # 资产负债表（时点值，Q4 年报值）
            total_assets = cfg["asset_base"] * growth
            total_equity = total_assets * cfg["equity_ratio"]
            total_liab = total_assets - total_equity
            current_assets = total_assets * 0.55
            current_liab = total_liab * 0.60
            cash = total_assets * cfg["cash_ratio"]
            inventory = total_assets * cfg["inventory_ratio"]
            fixed_assets = total_assets * 0.30
            st_borrow = total_assets * cfg["borrowing_ratio"] * 0.5
            lt_borrow = total_assets * cfg["borrowing_ratio"] * 0.5

            for q_month, q_type in quarters:
                rpt_date = date(fy, int(q_month[:2]), int(q_month[-2:]))

                # 检查是否已存在
                exist = (
                    db.query(FinancialStatement)
                    .filter_by(symbol=symbol, report_date=rpt_date, report_type=q_type)
                    .first()
                )
                if exist:
                    continue

                # 单季度收入（按比例分配，Q4 占比最大）
                q_weights = {"q1": 0.20, "semi_annual": 0.25, "q3": 0.25, "annual": 0.30}
                qw = q_weights.get(q_type, 0.25)
                q_rev = annual_rev * qw
                q_cost = q_rev * (1 - cfg["profit_margin"] - 0.15)
                q_profit = q_rev * cfg["profit_margin"]
                q_attr = q_profit * 0.92
                q_ocf = q_profit * 1.3
                q_capex = q_rev * cfg["capex_ratio"]
                q_div = annual_dividends * qw

                stmt = FinancialStatement(
                    symbol=symbol,
                    report_date=rpt_date,
                    report_type=q_type,
                    fiscal_year=fy,
                    currency="CNY",
                    data_source="mock",
                    # 资产
                    total_assets=Decimal(str(round(total_assets))),
                    current_assets=Decimal(str(round(current_assets))),
                    cash_and_equivalents=Decimal(str(round(cash))),
                    accounts_receivable=Decimal(str(round(annual_rev * 0.08))),
                    inventory=Decimal(str(round(inventory))),
                    fixed_assets=Decimal(str(round(fixed_assets))),
                    # 负债
                    total_liabilities=Decimal(str(round(total_liab))),
                    current_liabilities=Decimal(str(round(current_liab))),
                    short_term_borrowings=Decimal(str(round(st_borrow))),
                    long_term_borrowings=Decimal(str(round(lt_borrow))),
                    # 权益
                    total_equity=Decimal(str(round(total_equity))),
                    retained_earnings=Decimal(str(round(total_equity * 0.6))),
                    # 利润表（单季度）
                    operating_revenue=Decimal(str(round(q_rev))),
                    operating_cost=Decimal(str(round(q_cost))),
                    selling_expenses=Decimal(str(round(q_rev * 0.04))),
                    administrative_expenses=Decimal(str(round(q_rev * 0.03))),
                    r_and_d_expenses=Decimal(str(round(q_rev * cfg["rd_ratio"]))),
                    financial_expenses=Decimal(str(round(-q_rev * 0.005))),
                    interest_expense=Decimal(str(round(total_liab * 0.03 * qw))),
                    operating_profit=Decimal(str(round(q_profit))),
                    total_profit=Decimal(str(round(q_profit * 0.98))),
                    net_profit=Decimal(str(round(q_profit))),
                    net_profit_attr_parent=Decimal(str(round(q_attr))),
                    net_profit_excl_nonrecurring=Decimal(str(round(q_attr * 0.95))),
                    basic_eps=Decimal(str(round(q_attr / stock_info["total_shares"], 4))),
                    # 现金流（单季度）
                    net_operating_cashflow=Decimal(str(round(q_ocf))),
                    net_investing_cashflow=Decimal(str(round(-q_capex))),
                    net_financing_cashflow=Decimal(str(round(-q_div))),
                    capital_expenditure=Decimal(str(round(q_capex))),
                    dividends_paid=Decimal(str(round(q_div))),
                    ending_cash_balance=Decimal(str(round(cash))),
                )
                db.add(stmt)
                stmts_created += 1

        # ── 创建年报指标 ──
        for fy in years:
            fy_offset = fy - 2024
            growth = (1 + cfg["rev_growth"]) ** fy_offset

            # 本年全年数据
            rev = cfg["rev_base"] * growth
            cost = rev * (1 - cfg["profit_margin"] - 0.15)
            op_profit = rev * (cfg["profit_margin"] + 0.05)
            net_p = rev * cfg["profit_margin"]
            net_p_attr = net_p * 0.92
            ocf = net_p * 1.3
            capex = rev * cfg["capex_ratio"]

            total_assets = cfg["asset_base"] * growth
            total_equity = total_assets * cfg["equity_ratio"]
            total_liab = total_assets - total_equity
            current_as = total_assets * 0.55
            current_lb = total_liab * 0.60
            cash = total_assets * cfg["cash_ratio"]
            inv = total_assets * cfg["inventory_ratio"]
            div_paid = net_p_attr * cfg["dividend_payout"]

            # 上年数据（用于 YoY）
            prev_growth = (1 + cfg["rev_growth"]) ** (fy_offset - 1) if fy_offset > 0 else 1
            prev_rev = cfg["rev_base"] * prev_growth
            prev_net_attr = prev_rev * cfg["profit_margin"] * 0.92
            prev_assets = cfg["asset_base"] * prev_growth
            prev_equity = prev_assets * cfg["equity_ratio"]
            prev_op = prev_rev * (cfg["profit_margin"] + 0.05)

            exist_ind = (
                db.query(FinancialIndicator)
                .filter_by(symbol=symbol, report_date=date(fy, 12, 31), report_type="annual")
                .first()
            )
            if exist_ind:
                continue

            ind = FinancialIndicator(
                symbol=symbol,
                report_date=date(fy, 12, 31),
                report_type="annual",
                fiscal_year=fy,
                # 盈利能力
                roe=round(net_p_attr / total_equity, 6) if total_equity > 0 else None,
                roa=round(net_p / total_assets, 6) if total_assets > 0 else None,
                gross_margin=round((rev - cost) / rev, 6) if rev > 0 else None,
                net_margin=round(net_p_attr / rev, 6) if rev > 0 else None,
                operating_margin=round(op_profit / rev, 6) if rev > 0 else None,
                # 成长能力
                revenue_yoy=round((rev - prev_rev) / prev_rev, 6) if fy_offset > 0 else None,
                net_profit_yoy=round((net_p_attr - prev_net_attr) / prev_net_attr, 6) if fy_offset > 0 else None,
                operating_profit_yoy=round((op_profit - prev_op) / prev_op, 6) if fy_offset > 0 else None,
                # 偿债
                current_ratio=round(current_as / current_lb, 6) if current_lb > 0 else None,
                quick_ratio=round((cash + rev * 0.08) / current_lb, 6) if current_lb > 0 else None,
                debt_to_assets=round(total_liab / total_assets, 6) if total_assets > 0 else None,
                debt_to_equity=round(total_liab / total_equity, 6) if total_equity > 0 else None,
                interest_coverage=round(op_profit / (total_liab * 0.03), 2) if total_liab > 0 else None,
                # 营运
                asset_turnover=round(rev / total_assets, 6) if total_assets > 0 else None,
                # 估值
                fcf=round(ocf - capex),
                dividend_per_share=round(div_paid / stock_info["total_shares"], 4) if stock_info["total_shares"] > 0 else None,
                book_value_per_share=round(total_equity / stock_info["total_shares"], 4) if stock_info["total_shares"] > 0 else None,
            )
            db.add(ind)
            inds_created += 1

    db.commit()

    return APIResponse(
        message="测试数据注入完成",
        data={
            "stocks_created": stocks_created,
            "statements_created": stmts_created,
            "indicators_created": inds_created,
            "companies": ["猴子科技(100001)", "猪模块(200002)", "太空探索技术(300003)"],
        },
    )


# ═══════════════════════════════════════════════════════════════
# ETL 调试
# ═══════════════════════════════════════════════════════════════
@router.post("/data/debug-etl", response_model=APIResponse[dict])
def debug_etl(db: Session = Depends(get_db)):
    """调试端点：单步执行 ETL 并返回各阶段结果。"""
    from app.services.etl.fetcher import DataFetcher
    from app.services.etl.cleaner import DataCleaner
    from app.services.etl.loader import DataLoader

    symbol = "600519"
    fetcher = DataFetcher()
    cleaner = DataCleaner()
    result = {}

    # 1. 抓取
    try:
        data = fetcher.fetch_all_for_stock(symbol)
        result["fetch"] = {
            "balance": len(data.get("balance_sheet", [])),
            "income": len(data.get("income_statement", [])),
            "cashflow": len(data.get("cash_flow", [])),
        }
    except Exception as e:
        result["fetch_error"] = str(e)
        return APIResponse(data=result)

    # 2. 清洗
    bs = data.get("balance_sheet")
    inc = data.get("income_statement")
    cf = data.get("cash_flow")

    if bs is not None and len(bs) > 0:
        try:
            bs_clean = cleaner.clean_balance_sheet(bs, symbol)
            result["clean_bs"] = {"rows": len(bs_clean), "cols": list(bs_clean.columns)[:10]}
        except Exception as e:
            result["clean_bs_error"] = f"{type(e).__name__}: {e}"

    if inc is not None and len(inc) > 0:
        try:
            inc_clean = cleaner.clean_income_statement(inc, symbol)
            result["clean_inc"] = {"rows": len(inc_clean), "cols": list(inc_clean.columns)[:10]}
        except Exception as e:
            result["clean_inc_error"] = f"{type(e).__name__}: {e}"

    if cf is not None and len(cf) > 0:
        try:
            cf_clean = cleaner.clean_cash_flow(cf, symbol)
            result["clean_cf"] = {"rows": len(cf_clean), "cols": list(cf_clean.columns)[:10]}
        except Exception as e:
            result["clean_cf_error"] = f"{type(e).__name__}: {e}"

    # 3. 尝试入库 1 条
    try:
        if bs is not None and len(bs) > 0 and inc is not None and len(inc) > 0 and cf is not None and len(cf) > 0:
            bs_clean = cleaner.clean_balance_sheet(bs, symbol)
            inc_clean = cleaner.clean_income_statement(inc, symbol)
            cf_clean = cleaner.clean_cash_flow(cf, symbol)
            merged = cleaner.merge_statements(bs_clean, inc_clean, cf_clean, symbol)
            result["merged"] = {"rows": len(merged), "cols": list(merged.columns)[:10]}
            loader = DataLoader(db)
            # 逐条试第一条
            import traceback
            first = merged.iloc[0].to_dict()
            result["first"] = {k: str(v)[:50] for k, v in first.items() if v is not None}
            try:
                loader._upsert(FinancialStatement, first, ["symbol","report_date","report_type"])
                result["test_upsert"] = "ok"
            except Exception as e:
                result["test_upsert"] = f"{type(e).__name__}: {e}"
                result["traceback"] = traceback.format_exc()[-500:]
            db.rollback()
            count = loader.upsert_financials(merged)
            result["upsert"] = {"success": True, "inserted": count}
        else:
            result["skip"] = "三表不全，无合并数据"
    except Exception as e:
        result["upsert_error"] = f"{type(e).__name__}: {e}"

    return APIResponse(data=result)
