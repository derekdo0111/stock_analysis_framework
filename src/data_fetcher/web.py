"""Web 数据源 — 从网络获取行业数据、市场数据等（非 Tushare 来源）。

用途:
- 补充 Tushare 不提供的字段（如行业排名、PE-band、宏观数据）
- 作为 Tushare/akshare 的降级方案
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from loguru import logger


class WebDataSource:
    """Web 爬虫数据源。

    当前为占位实现，后续可接入:
    - EastMoney API (东方财富)
    - JQData / RiceQuant
    - 公开 Web 页面解析
    """

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._available: bool = False

    @property
    def name(self) -> str:
        return "web"

    def is_available(self) -> bool:
        return self._available

    def fetch_industry_comparison(
        self,
        ts_code: str,
        industry: str = "",
    ) -> Optional[pd.DataFrame]:
        """获取同行业对比数据。

        Args:
            ts_code: 股票代码
            industry: 行业名称（用于筛选同行业公司）

        Returns:
            DataFrame 或 None
        """
        logger.warning("Web 数据源尚未实现，返回 None")
        return None

    def fetch_market_data(
        self,
        indicator: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> Optional[pd.DataFrame]:
        """获取市场宏观数据（利率、CPI、PMI 等）。"""
        logger.warning("Web 数据源尚未实现，返回 None")
        return None


__all__ = ["WebDataSource"]
