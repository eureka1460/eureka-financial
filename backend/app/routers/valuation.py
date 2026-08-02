"""
估值模型 API 路由。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.valuation import (
    DCFRequest, DCFResponse,
    DDMRequest, DDMResponse,
)
from app.services.valuation import ValuationEngine

router = APIRouter(prefix="/api/v1", tags=["valuation"])


@router.post("/valuation/dcf", response_model=APIResponse[DCFResponse])
def dcf_valuation(
    request: DCFRequest,
    db: Session = Depends(get_db),
):
    """DCF 自由现金流折现估值。

    任何参数传 null 则自动从数据库填充。
    返回计算过程和最终估值。
    """
    engine = ValuationEngine(db)
    result = engine.calculate_dcf(request)
    return APIResponse(data=result)


@router.post("/valuation/ddm", response_model=APIResponse[DDMResponse])
def ddm_valuation(
    request: DDMRequest,
    db: Session = Depends(get_db),
):
    """DDM 股利折现估值。

    任何参数传 null 则自动从数据库填充。
    返回计算过程和最终估值。
    """
    engine = ValuationEngine(db)
    result = engine.calculate_ddm(request)
    return APIResponse(data=result)
