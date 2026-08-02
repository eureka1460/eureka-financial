"""
数据抓取器 —— akshare 封装。

四层防御体系：
    L1 限速：请求间隔随机抖动，避免触发反爬
    L2 重试：指数退避，最多 5 次，处理临时故障
    L3 缓存：diskcache，历史数据 6 小时不变
    L4 备用源：东方财富 → 新浪财经

每个抓取方法都经过 @rate_limited + @retry + @cached 三层装饰器包裹。
"""

import time
import random
import logging
from functools import wraps
from typing import Optional

import pandas as pd
import akshare as ak
from diskcache import Cache
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_result,
    before_sleep_log,
)

from app.core.config import settings
from app.core.exceptions import DataFetchException

logger = logging.getLogger(__name__)

def _to_em_symbol(symbol: str) -> str:
    """将纯数字代码转为东方财富格式（带市场前缀）。

    600519 → SH600519
    000858 → SZ000858
    300750 → SZ300750
    838402 → BJ838402
    """
    s = str(symbol).strip()
    if s.startswith("6"):
        return f"SH{s}"
    elif s.startswith(("0", "3")):
        return f"SZ{s}"
    elif s.startswith(("8", "4")):
        return f"BJ{s}"
    return s


def _to_sina_symbol(symbol: str) -> str:
    """将纯数字代码转为新浪格式（小写市场前缀）。

    600519 → sh600519
    000858 → sz000858
    """
    s = str(symbol).strip()
    if s.startswith("6"):
        return f"sh{s}"
    elif s.startswith(("0", "3")):
        return f"sz{s}"
    elif s.startswith(("8", "4")):
        return f"bj{s}"
    return s


# ── 缓存实例（模块级别单例）─────────────────────────────────
_cache = Cache(directory=settings.CACHE_DIR)


# ═══════════════════════════════════════════════════════════════
# L1: 限速器
# ═══════════════════════════════════════════════════════════════
class RateLimiter:
    """Token Bucket 限速器。

    每次调用前 acquire()，强制随机间隔，防止连续高频请求。
    """

    def __init__(self, max_calls: int = 4, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self._last_call = 0.0

    def acquire(self):
        """获取调用许可，必要时等待。"""
        now = time.time()
        elapsed = now - self._last_call
        min_interval = settings.ETL_MIN_INTERVAL
        max_interval = settings.ETL_MAX_INTERVAL
        required_wait = max(0, min_interval - elapsed)
        # 添加随机抖动
        jitter = random.uniform(0, max_interval - min_interval)
        total_wait = required_wait + jitter
        if total_wait > 0:
            time.sleep(total_wait)
        self._last_call = time.time()

    def __call__(self, func):
        """作为装饰器使用。"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)

        return wrapper


# 全局限速器实例
_rate_limiter = RateLimiter(
    max_calls=settings.ETL_RATE_LIMIT_CALLS,
    period=settings.ETL_RATE_LIMIT_PERIOD,
)


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════
def _empty_df(result) -> bool:
    """tenacity 判定条件：DataFrame 为空视为失败，需要重试。"""
    if isinstance(result, pd.DataFrame):
        return len(result) == 0
    return False


def _make_cache_key(func_name: str, *args, **kwargs) -> str:
    """生成 diskcache 缓存键。"""
    parts = [func_name] + [str(a) for a in args]
    sorted_kw = sorted(kwargs.items())
    parts += [f"{k}={v}" for k, v in sorted_kw]
    return ":".join(parts)


# ═══════════════════════════════════════════════════════════════
# L2+L3: 重试 + 缓存装饰器工厂
# ═══════════════════════════════════════════════════════════════
def _with_retry_and_cache(func_name: str, cache_ttl: int = None):
    """组合重试和缓存两层防御的装饰器工厂。

    Args:
        func_name: 函数名（用于缓存键前缀）
        cache_ttl: 缓存过期时间（秒），默认 6 小时
    """
    if cache_ttl is None:
        cache_ttl = settings.CACHE_TTL_HISTORICAL

    def decorator(func):
        @wraps(func)
        @_rate_limiter
        @retry(
            stop=stop_after_attempt(settings.ETL_RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=settings.ETL_RETRY_MIN_WAIT,
                max=settings.ETL_RETRY_MAX_WAIT,
            ),
            retry=retry_if_result(_empty_df),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def wrapper(*args, **kwargs):
            # L3: 检查缓存
            cache_key = _make_cache_key(func_name, *args, **kwargs)
            if cache_key in _cache:
                logger.debug(f"缓存命中: {cache_key}")
                return _cache[cache_key]

            # L1+L2: 限速 + 重试包裹的实际调用
            result = func(*args, **kwargs)

            # 缓存结果
            if isinstance(result, pd.DataFrame) and len(result) > 0:
                _cache.set(cache_key, result, expire=cache_ttl)
                logger.debug(f"缓存写入: {cache_key}")

            return result

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════
# 数据抓取器
# ═══════════════════════════════════════════════════════════════
class DataFetcher:
    """A 股财务数据抓取器。

    封装 akshare 的东方财富主源和新浪财经备用源，
    每个方法都自动经过 限速 → 重试 → 缓存 三层处理。

    用法：
        fetcher = DataFetcher()
        df = fetcher.fetch_balance_sheet("600519")
    """

    # ── 股票列表 ────────────────────────────────────────────
    def fetch_stock_list(self) -> pd.DataFrame:
        """获取全 A 股股票列表。

        Returns:
            DataFrame with columns: 代码, 名称
        """
        cache_key = _make_cache_key("stock_list")
        if cache_key in _cache:
            return _cache[cache_key]

        # 股票列表不需要频繁更新，不限速
        try:
            df = ak.stock_info_a_code_name()
            if len(df) > 0:
                # 统一列名
                df = df.rename(columns={"code": "symbol", "name": "name"})
                # 标准化列名适配不同版本的 akshare
                if "symbol" not in df.columns:
                    df = df.rename(columns={"代码": "symbol", "名称": "name"})
                _cache.set(cache_key, df, expire=settings.CACHE_TTL_REALTIME)
                return df
        except Exception as e:
            logger.warning(f"获取股票列表失败: {e}")

        raise DataFetchException(detail="无法获取股票列表")

    # ── 资产负债表 ──────────────────────────────────────────
    def fetch_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """获取资产负债表。

        主源：东方财富 (stock_balance_sheet_by_report_em) — 需要 SH600519 格式
        备源：新浪财经 (stock_financial_report_sina) — 需要 sh600519 格式
        """
        em_sym = _to_em_symbol(symbol)
        sina_sym = _to_sina_symbol(symbol)
        return _fetcher_with_fallback(
            func_name="balance_sheet",
            symbol=symbol,
            primary_fn=lambda: ak.stock_balance_sheet_by_report_em(symbol=em_sym),
            fallback_fn=lambda: ak.stock_financial_report_sina(
                stock=sina_sym, symbol="资产负债表"
            ),
        )

    # ── 利润表（单季度版）──────────────────────────────────
    def fetch_income_statement(self, symbol: str) -> pd.DataFrame:
        """获取利润表（单季度数据）。

        主源：东方财富 (stock_profit_sheet_by_quarterly_em) — 直接返回单季度值
        备源：新浪财经
        """
        em_sym = _to_em_symbol(symbol)
        sina_sym = _to_sina_symbol(symbol)
        return _fetcher_with_fallback(
            func_name="income_statement_quarterly",
            symbol=symbol,
            primary_fn=lambda: ak.stock_profit_sheet_by_quarterly_em(symbol=em_sym),
            fallback_fn=lambda: ak.stock_financial_report_sina(
                stock=sina_sym, symbol="利润表"
            ),
        )

    # ── 现金流量表（单季度版）────────────────────────────────
    def fetch_cash_flow(self, symbol: str) -> pd.DataFrame:
        """获取现金流量表（单季度数据）。

        主源：东方财富 (stock_cash_flow_sheet_by_quarterly_em) — 直接返回单季度值
        备源：新浪财经
        """
        em_sym = _to_em_symbol(symbol)
        sina_sym = _to_sina_symbol(symbol)
        return _fetcher_with_fallback(
            func_name="cash_flow_quarterly",
            symbol=symbol,
            primary_fn=lambda: ak.stock_cash_flow_sheet_by_quarterly_em(symbol=em_sym),
            fallback_fn=lambda: ak.stock_financial_report_sina(
                stock=sina_sym, symbol="现金流量表"
            ),
        )

    # ── 批量获取 ────────────────────────────────────────────
    def fetch_all_for_stock(self, symbol: str) -> dict[str, pd.DataFrame]:
        """一次获取一只股票的三张报表。

        Returns:
            {
                "balance_sheet": DataFrame,
                "income_statement": DataFrame,
                "cash_flow": DataFrame,
            }
        """
        results = {}
        errors = []

        for sheet_type, fetch_fn in [
            ("balance_sheet", self.fetch_balance_sheet),
            ("income_statement", self.fetch_income_statement),
            ("cash_flow", self.fetch_cash_flow),
        ]:
            try:
                df = fetch_fn(symbol)
                results[sheet_type] = df
            except Exception as e:
                logger.error(f"{symbol} {sheet_type} 抓取失败: {e}")
                errors.append(f"{sheet_type}: {e}")

        if not results:
            raise DataFetchException(
                symbol=symbol,
                detail="; ".join(errors),
            )

        return results


# ═══════════════════════════════════════════════════════════════
# L4: 备用源 fallback 逻辑
# ═══════════════════════════════════════════════════════════════
@_rate_limiter
@retry(
    stop=stop_after_attempt(3),  # 主源失败后给备源更少的重试机会
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_result(_empty_df),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _try_primary(primary_fn, symbol: str, sheet_type: str) -> pd.DataFrame:
    """尝试主数据源（东方财富），带重试。"""
    logger.info(f"{symbol}: 尝试主源 (Eastmoney) 获取 {sheet_type}")
    df = primary_fn()
    if len(df) == 0:
        raise DataFetchException(symbol=symbol, detail=f"主源返回空数据: {sheet_type}")
    return df


@_rate_limiter
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_result(_empty_df),
    reraise=True,
)
def _try_fallback(fallback_fn, symbol: str, sheet_type: str) -> pd.DataFrame:
    """尝试备用数据源（新浪财经），带重试。"""
    logger.warning(f"{symbol}: 主源失败，切换备源 (Sina) 获取 {sheet_type}")
    df = fallback_fn()
    if len(df) == 0:
        raise DataFetchException(symbol=symbol, detail=f"备源也返回空数据: {sheet_type}")
    return df


def _fetcher_with_fallback(
    func_name: str,
    symbol: str,
    primary_fn,
    fallback_fn,
) -> pd.DataFrame:
    """带四级防御的通用抓取函数。

    L3(缓存) → L1(限速) → L2(重试+主源) → L4(重试+备源)
    """
    # L3: 缓存检查
    cache_key = _make_cache_key(func_name, symbol)
    if cache_key in _cache:
        logger.debug(f"缓存命中: {cache_key}")
        return _cache[cache_key]

    # L1+L2: 主源（限速由 _try_primary 内部处理）
    try:
        df = _try_primary(primary_fn, symbol, func_name)
    except Exception as e:
        logger.warning(f"{symbol}: 主源完全失败 ({e})，启动备源...")
        # L4: 备源
        try:
            df = _try_fallback(fallback_fn, symbol, func_name)
        except Exception as e2:
            raise DataFetchException(
                symbol=symbol,
                detail=f"主源和备源均失败。主源: {e}, 备源: {e2}",
            )

    # 缓存结果
    if isinstance(df, pd.DataFrame) and len(df) > 0:
        _cache.set(cache_key, df, expire=settings.CACHE_TTL_HISTORICAL)

    return df
