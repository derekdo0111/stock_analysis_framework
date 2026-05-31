"""回测验证层 — Walk-Forward 分红验证"""

from src.backtest.window_manager import WindowManager, BacktestWindow, DEFAULT_WINDOWS
from src.backtest.pipeline_runner import PipelineRunner, WindowResult
from src.backtest.dividend_validator import DividendValidator, DividendValidation
from src.backtest.statistics import BacktestStatistics, WindowStats, CrossWindowSummary
from src.backtest.report import BacktestReportGenerator

__all__ = [
    "WindowManager",
    "BacktestWindow",
    "DEFAULT_WINDOWS",
    "PipelineRunner",
    "WindowResult",
    "DividendValidator",
    "DividendValidation",
    "BacktestStatistics",
    "WindowStats",
    "CrossWindowSummary",
    "BacktestReportGenerator",
]
