"""通用工具模块 — 异常/日志/重试/配置/常量/校验"""

from src.core.utils.exceptions import (
    StockAnalysisError,
    DataFetchError,
    DataValidationError,
    CalculationError,
    ConfigError,
    HardGateRejection,
    LLMError,
)
from src.core.utils.logger import logger, setup_logger
from src.core.utils.retry import api_retry, with_fallback
from src.core.utils.config import AppConfig
from src.core.utils.constants import VERSION, DEFAULT_LOOKBACK_YEARS
from src.core.utils.validators import validate_ts_code, safe_divide, clip_score

__all__ = [
    # exceptions
    "StockAnalysisError",
    "DataFetchError",
    "DataValidationError",
    "CalculationError",
    "ConfigError",
    "HardGateRejection",
    "LLMError",
    # logger
    "logger",
    "setup_logger",
    # retry
    "api_retry",
    "with_fallback",
    # config
    "AppConfig",
    # constants
    "VERSION",
    "DEFAULT_LOOKBACK_YEARS",
    # validators
    "validate_ts_code",
    "safe_divide",
    "clip_score",
]
