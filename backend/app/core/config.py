"""
应用配置中心。

所有可调参数集中在此，通过环境变量或 .env 文件覆盖默认值。
使用 pydantic-settings 实现类型安全的配置管理。
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录：backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """应用全局配置。

    每个配置项都可被环境变量覆盖，例如：
        export DATABASE_URL=postgresql://...
        export ETL_RATE_LIMIT_CALLS=2
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            # TODO: 改为环境变量方式
            self.DATABASE_URL = "mysql+pymysql://root1:14601554%25qin@sh-cynosdbmysql-grp-miggvbtm.sql.tencentcdb.com:26657/cloud1-d2gaskev55a202518"

    # ── 数据库 ────────────────────────────────────────────
    # 开发阶段默认 SQLite，云托管部署时设 MYSQL_HOST 切 MySQL
    MYSQL_HOST: str = ""
    MYSQL_PORT: str = "3306"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "eureka"
    # 完整数据库 URL（自动拼接，也可直接设置）
    DATABASE_URL: str = ""

    # ── 缓存 ──────────────────────────────────────────────
    CACHE_DIR: str = str(PROJECT_ROOT / "data" / "cache")
    # 历史财务数据缓存 6 小时（一般不会变）
    CACHE_TTL_HISTORICAL: int = 21600
    # 实时/元数据缓存 30 分钟
    CACHE_TTL_REALTIME: int = 1800

    # ── ETL 限速 ──────────────────────────────────────────
    # 每秒最大请求次数（针对 akshare 底层的东方财富接口）
    ETL_RATE_LIMIT_CALLS: int = 4
    # 限速时间窗口（秒）
    ETL_RATE_LIMIT_PERIOD: float = 1.0
    # 请求之间最小间隔（秒），0.5-1.5 随机抖动
    ETL_MIN_INTERVAL: float = 0.5
    ETL_MAX_INTERVAL: float = 1.5
    # 失败重试次数
    ETL_RETRY_ATTEMPTS: int = 5
    # 重试最小/最大等待时间（秒）
    ETL_RETRY_MIN_WAIT: int = 1
    ETL_RETRY_MAX_WAIT: int = 60

    # ── 数据抓取 ──────────────────────────────────────────
    # 默认抓取年数
    DEFAULT_FETCH_YEARS: int = 5
    # ETL 批量处理：每批处理的股票数量
    ETL_BATCH_SIZE: int = 50

    # ── API 限流 ──────────────────────────────────────────
    # 公开端点：每分钟每 IP 最大请求数
    RATE_LIMIT_PUBLIC: int = 100
    # 计算密集型端点（筛选/估值）：每分钟每 IP 最大请求数
    RATE_LIMIT_HEAVY: int = 30

    # ── 微信登录（后续阶段启用）────────────────────────────
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7

    # ── 服务器 ────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True


# 全局单例
settings = Settings()
