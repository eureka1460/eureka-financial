"""
数据库连接管理。

为 SQLite 启用 WAL 模式以支持并发读写（ETL 写 + API 读）。
通过 SQLAlchemy 2.x 风格创建引擎和会话工厂。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# ── Engine ─────────────────────────────────────────────────
# SQLite 专用参数：
#   - check_same_thread=False  允许跨线程使用（FastAPI 的 async 线程池需要）
#   - WAL 模式                  写操作不阻塞读操作
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,                # 生产环境设为 False，调试时可临时开启
    connect_args=connect_args,
    pool_pre_ping=True,        # 连接前检测是否存活
)

# SQLite WAL 模式：提升并发性能
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# ── Session ────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ── Base ───────────────────────────────────────────────────
# 所有 ORM 模型继承此类
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：每个请求获取独立的数据库会话。

    用法：
        @app.get("/stocks")
        def list_stocks(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
