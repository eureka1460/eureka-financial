"""
自定义异常类。

每个异常类对应一种已知的业务错误场景。
在 main.py 中注册全局异常处理器，将异常转换为标准 JSON 响应。
"""


class AppBaseException(Exception):
    """应用基础异常，所有自定义异常继承此类。"""

    def __init__(self, message: str = "", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)


class DataFetchException(AppBaseException):
    """外部数据源不可用。

    触发场景：
        - akshare 所有数据源（Eastmoney + Sina）均请求失败
        - 网络断开
        - 数据源返回空 DataFrame
    """

    def __init__(self, symbol: str = "", detail: str = ""):
        msg = f"数据抓取失败{f': {symbol}' if symbol else ''}"
        super().__init__(message=msg, detail=detail)


class StockNotFoundException(AppBaseException):
    """股票代码不存在于数据库中。"""

    def __init__(self, symbol: str):
        super().__init__(
            message=f"股票代码不存在: {symbol}",
            detail=f"symbol '{symbol}' not found in stocks table",
        )


class DataValidationException(AppBaseException):
    """ETL 数据校验失败。

    触发场景：
        - 总资产 <= 0
        - 资产负债表不平衡（|资产 − 负债 − 权益| > 1%）
        - DataFrame 空
    """

    def __init__(self, symbol: str = "", detail: str = ""):
        msg = f"数据校验失败{f': {symbol}' if symbol else ''}"
        super().__init__(message=msg, detail=detail)


class ScreeningExpressionError(AppBaseException):
    """筛选表达式解析或执行错误。

    触发场景：
        - 用户输入的表达式语法错误
        - 表达式引用了不存在的指标
        - 表达式类型不匹配（如字符串 * 数字）
    """

    def __init__(self, expression: str = "", detail: str = ""):
        msg = f"筛选表达式错误{f': {expression}' if expression else ''}"
        super().__init__(message=msg, detail=detail)


class ValuationParameterError(AppBaseException):
    """估值模型参数不合法。

    触发场景：
        - WACC <= 0 或 >= 100%
        - 永续增长率 >= WACC
        - 预测年数为 0
    """

    def __init__(self, detail: str = ""):
        super().__init__(message="估值参数不合法", detail=detail)
