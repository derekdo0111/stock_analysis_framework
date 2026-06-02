"""数据源适配器基类 — 统一接口，支持 Tushare/akshare/Web 多适配器。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataSourceAdapter(ABC):
    """数据源适配器抽象基类。

    所有数据源（Tushare/akshare/Web）必须实现此接口。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称。"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用。"""
        ...

    # ── Required interfaces (所有适配器必须实现) ──────────

    @abstractmethod
    def stock_basic(self, **kwargs) -> pd.DataFrame:
        """股票基本信息。"""
        ...

    @abstractmethod
    def daily(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """日线行情。"""
        ...

    @abstractmethod
    def income(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """利润表。"""
        ...

    # ── Optional interfaces (子类按需实现) ─────────────────

    def balancesheet(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """资产负债表。"""
        return pd.DataFrame()

    def cashflow(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """现金流量表。"""
        return pd.DataFrame()

    def fina_indicator(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """财务指标。"""
        return pd.DataFrame()

    def dividend(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """分红数据。"""
        return pd.DataFrame()

    def daily_basic(self, ts_code: str, **kwargs) -> pd.DataFrame:
        """每日指标。"""
        return pd.DataFrame()


__all__ = ["DataSourceAdapter"]
