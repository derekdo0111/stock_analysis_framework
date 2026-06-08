"""自定义异常层次结构。"""

from __future__ import annotations


class StockAnalysisError(Exception):
    """框架顶级异常。"""
    pass


class DataFetchError(StockAnalysisError):
    """数据获取失败（网络/API/认证）。"""
    pass


class DataValidationError(StockAnalysisError):
    """数据校验失败。"""
    pass


class CalculationError(StockAnalysisError):
    """计算过程异常。"""
    pass


class ConfigError(StockAnalysisError):
    """配置加载或解析错误。"""
    pass


class HardGateRejection(StockAnalysisError):
    """HardGate 否决异常（携带原因）。"""
    def __init__(self, ts_code: str, reason: str):
        self.ts_code = ts_code
        self.reason = reason
        super().__init__(f"[{ts_code}] HardGate 否决: {reason}")


class LLMError(StockAnalysisError):
    """LLM 调用异常。"""
    pass


__all__ = [
    "StockAnalysisError",
    "DataFetchError",
    "DataValidationError",
    "CalculationError",
    "ConfigError",
    "HardGateRejection",
    "LLMError",
]
