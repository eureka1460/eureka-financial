"""
数据库连接管理。

支持 SQLite（开发）和 MySQL（生产，云开发托管数据库）。
通过 SQLAlchemy 2.x 风格创建引擎和会话工厂。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# ── Engine ─────────────────────────────────────────────────
is_sqlite = "sqlite" in settings.DATABASE_URL

connect_args = {}
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}

if is_sqlite:
    connect_args = {"check_same_thread": False}
else:
    # MySQL 配置
    connect_args = {"charset": "utf8mb4"}
    engine_kwargs.update({
        "pool_size": 3,
        "pool_recycle": 600,
    })

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

# SQLite WAL 模式
if is_sqlite:
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
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：每个请求获取独立的数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
