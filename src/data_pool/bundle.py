"""
StockDataBundle — 统一数据载体。

全部计算模块从 bundle 读取数据，不再直接调用 TushareClient。
只有 DataPoolOrchestrator 有权限拉取 Tushare 数据并写入缓存。

v0.19: 新增 3 个字段 — dividend_commitment, buyback_cancellation, restricted_cash。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StockDataBundle:
    """持有单只股票管线所需的全部 DataFrame + v0.19 提取数据。"""

    ts_code: str
    name: str = ""
    industry: str = ""

    # ── 各数据集的完整 DataFrame（已按 ts_code 预过滤） ──
    stock_basic: pd.DataFrame = field(default_factory=pd.DataFrame)
    fina_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily_basic: pd.DataFrame = field(default_factory=pd.DataFrame)
    fina_indicator: pd.DataFrame = field(default_factory=pd.DataFrame)
    income: pd.DataFrame = field(default_factory=pd.DataFrame)
    balancesheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    dividend: pd.DataFrame = field(default_factory=pd.DataFrame)
    repurchase: pd.DataFrame = field(default_factory=pd.DataFrame)
    pledge_stat: pd.DataFrame = field(default_factory=pd.DataFrame)

    # ── v0.19: Web+LLM 提取数据 ──
    dividend_commitment: Any = None  # DividendCommitment | None
    buyback_cancellation: Any = None  # BuybackCancellation | None
    restricted_cash: float = 0.0      # 限制性货币（万元）
