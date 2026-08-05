"""
FastAPI 应用入口。

创建 app 实例、注册中间件、异常处理器和路由。
启动命令：uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, Base
# 导入所有模型，确保 Base.metadata 在 create_all 时能找到全部表
import app.models  # noqa: F401
from app.core.exceptions import (
    AppBaseException,
    DataFetchException,
    StockNotFoundException,
    DataValidationException,
    ScreeningExpressionError,
    ValuationParameterError,
)

# ── App 实例 ───────────────────────────────────────────────
app = FastAPI(
    title="Eureka Stock Analyzer",
    description="A股财报选股与估值分析 API",
    version="0.1.0",
    docs_url="/docs",           # Swagger 文档
    redoc_url="/redoc",         # ReDoc 文档
)

# ── 注册路由 ───────────────────────────────────────────────
from app.routers import stocks, financials, data, screener, valuation  # noqa: E402

app.include_router(stocks.router)
app.include_router(financials.router)
app.include_router(data.router)
app.include_router(screener.router)
app.include_router(valuation.router)

# ── CORS 中间件 ────────────────────────────────────────────
# 开发阶段允许所有来源，生产环境应限制为小程序域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 启动事件 ───────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """应用启动时自动创建数据库表，空库时注入测试数据。"""
    Base.metadata.create_all(bind=engine)
    # 空库自动注入 mock 数据
    from app.core.database import SessionLocal
    from app.models.stocks import Stock
    db = SessionLocal()
    try:
        if db.query(Stock).count() == 0:
            from app.routers.data import seed_mock_data
            seed_mock_data(db)
    finally:
        db.close()


# ── 健康检查 ───────────────────────────────────────────────
@app.get("/api/v1/test-akshare")
def test_akshare():
    """测试 aksale 是否能正常抓取数据。"""
    try:
        import akshare as ak
        df = ak.stock_profit_sheet_by_quarterly_em(symbol="SH600519")
        return JSONResponse({
            "code": 200,
            "message": f"ok, {len(df)} rows",
            "data": {"columns": list(df.columns), "rows": len(df)},
        })
    except Exception as e:
        return JSONResponse({
            "code": 500,
            "message": f"aksale 测试失败: {type(e).__name__}: {e}",
        })


@app.get("/")
@app.get("/api/v1/health")
def health_check():
    """健康检查端点。"""
    # 测试外网连通性
    import urllib.request
    net_ok = False
    try:
        urllib.request.urlopen("https://www.baidu.com", timeout=5)
        net_ok = True
    except Exception:
        pass
    return JSONResponse(
        content={
            "code": 200,
            "message": "ok",
            "data": {
                "version": "0.1.0",
                "database": settings.DATABASE_URL.split("///")[-1],
                "network": "ok" if net_ok else "blocked",
            },
        }
    )


# ── 全局异常处理器 ─────────────────────────────────────────
@app.exception_handler(AppBaseException)
async def app_base_exception_handler(request: Request, exc: AppBaseException):
    """所有自定义异常的基类处理器。"""
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": exc.message,
            "detail": exc.detail or None,
        },
    )


@app.exception_handler(DataFetchException)
async def data_fetch_exception_handler(request: Request, exc: DataFetchException):
    """外部数据源不可用 → 502。"""
    return JSONResponse(
        status_code=502,
        content={
            "code": 502,
            "message": exc.message,
            "detail": exc.detail or "外部数据源暂时不可用，请稍后重试",
        },
    )


@app.exception_handler(StockNotFoundException)
async def stock_not_found_handler(request: Request, exc: StockNotFoundException):
    """股票不存在 → 404。"""
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "message": exc.message,
            "detail": exc.detail or None,
        },
    )


@app.exception_handler(DataValidationException)
async def data_validation_handler(request: Request, exc: DataValidationException):
    """数据校验失败 → 422。"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": exc.message,
            "detail": exc.detail or None,
        },
    )


@app.exception_handler(ScreeningExpressionError)
async def screening_error_handler(request: Request, exc: ScreeningExpressionError):
    """筛选表达式错误 → 400。"""
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": exc.message,
            "detail": exc.detail or None,
        },
    )


@app.exception_handler(ValuationParameterError)
async def valuation_param_handler(request: Request, exc: ValuationParameterError):
    """估值参数错误 → 400。"""
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": exc.message,
            "detail": exc.detail or None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底处理器：未预期的异常 → 500。"""
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )
