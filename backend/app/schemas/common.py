"""
通用 API 响应模型。

所有接口的统一 JSON 包装格式。
"""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from fastapi import Query

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """标准 API 响应包装。

    所有接口都返回此格式：
    {"code": 200, "message": "success", "data": {...}}
    """

    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据包装。

    items: 当前页数据列表
    total: 总数
    page: 当前页码
    page_size: 每页数量
    """

    items: list[T]
    total: int
    page: int
    page_size: int


class PaginationParams:
    """分页请求参数依赖。

    用法：
        @app.get("/stocks")
        def list_stocks(pagination: PaginationParams = Depends()):
            ...
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
