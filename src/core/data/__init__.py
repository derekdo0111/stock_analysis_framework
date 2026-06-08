"""数据获取层 — Tushare Adapter + Web + 编排器 + LLM 提取器"""

from src.core.data.tushare_client import (
    TushareClient,
    TushareAdapterError,
    RateLimitError,
    TokenInvalidError,
)
from src.core.data.base import DataSourceAdapter
from src.core.data.web import WebDataSource
from src.core.data.web_extractor import WebExtractor, DividendCommitment, BuybackCancellation
from src.core.data.orchestrator import DataPoolOrchestrator, SnapshotResult

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

