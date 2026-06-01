"""数据获取层 — Tushare Adapter + Web + 编排器 + LLM 提取器"""

from src.data_fetcher.tushare_client import (
    TushareClient,
    TushareAdapterError,
    RateLimitError,
    TokenInvalidError,
)
from src.data_fetcher.base import DataSourceAdapter
from src.data_fetcher.web import WebDataSource
from src.data_fetcher.web_extractor import WebExtractor, DividendCommitment, BuybackCancellation
from src.data_fetcher.orchestrator import DataPoolOrchestrator, SnapshotResult

__all__ = [
    "TushareClient",
    "TushareAdapterError",
    "RateLimitError",
    "TokenInvalidError",
    "DataSourceAdapter",
    "WebDataSource",
    "WebExtractor",
    "DividendCommitment",
    "BuybackCancellation",
    "DataPoolOrchestrator",
    "SnapshotResult",
]

