"""
选股筛选 API 路由。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.screener import ScreenerRequest, ScreenerResultItem
from app.services.screener import ScreenerEngine

router = APIRouter(prefix="/api/v1", tags=["screener"])


@router.post(
    "/screener/search",
    response_model=APIResponse[PaginatedData[ScreenerResultItem]],
)
def search(
    request: ScreenerRequest,
    db: Session = Depends(get_db),
):
    """多条件选股筛选。

    支持单指标条件、多指标运算表达式、连续 N 年逻辑、AND/OR 组合。
    """
    engine = ScreenerEngine(db)
    result = engine.search(request)

    return APIResponse(
        data=PaginatedData(
            items=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    )
