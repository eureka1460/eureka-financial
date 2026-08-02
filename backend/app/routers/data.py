"""
数据同步管理 API 路由。

提供手动触发 ETL 同步和查询同步状态。
"""

import threading
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
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
