"""
通用财务比率计算 — 杜邦分析 / CAGR / 分位数。

不依赖龟龟策略逻辑，可复用于任何财务分析场景。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class DuPontResult:
    """杜邦分析结果。"""
    roe: float = 0.0
    net_margin: float = 0.0         # 净利润率
    asset_turnover: float = 0.0     # 总资产周转率
    equity_multiplier: float = 0.0  # 权益乘数
    roe_check: float = 0.0          # 验算: net_margin × turnover × multiplier
    period: str = ""                # 报告期


@dataclass
class CAGRResult:
    """CAGR 计算结果。"""
    metric_name: str
    start_value: float
    end_value: float
    years: int
    cagr: float = 0.0
    trend: str = ""  # "上升" / "下降" / "持平"


# ── 杜邦分析 ────────────────────────────────────────────────

def dupont_analysis(
    net_profit: float,
    revenue: float,
    total_assets: float,
    equity: float,
    period: str = "",
) -> DuPontResult:
    """标准杜邦分解 ROE = 净利润率 × 总资产周转率 × 权益乘数。

    Args:
        net_profit: 净利润
        revenue: 营业总收入
        total_assets: 总资产
        equity: 股东权益
        period: 报告期标签

    Returns:
        DuPontResult with decomposed ROE
    """
    if revenue == 0 or total_assets == 0 or equity == 0:
        return DuPontResult(period=period)

    net_margin = net_profit / revenue
    asset_turnover = revenue / total_assets
    equity_multiplier = total_assets / equity

    return DuPontResult(
        roe=net_profit / equity,
        net_margin=net_margin,
        asset_turnover=asset_turnover,
        equity_multiplier=equity_multiplier,
        roe_check=net_margin * asset_turnover * equity_multiplier,
        period=period,
    )


# ── CAGR ───────────────────────────────────────────────────

def calculate_cagr(
    start_value: float,
    end_value: float,
    years: int,
    metric_name: str = "",
) -> CAGRResult:
    """计算复合年增长率。

    CAGR = (end / start) ^ (1/years) - 1

    Args:
        start_value: 起始值
        end_value: 结束值
        years: 间隔年数
        metric_name: 指标名称

    Returns:
        CAGRResult
    """
    if years <= 0:
        return CAGRResult(
            metric_name=metric_name,
            start_value=start_value,
            end_value=end_value,
            years=years,
            cagr=0.0,
        )

    if start_value <= 0:
        return CAGRResult(
            metric_name=metric_name,
            start_value=start_value,
            end_value=end_value,
            years=years,
            cagr=float("nan"),
            trend="N/A (起始值非正)",
        )

    cagr = (end_value / start_value) ** (1.0 / years) - 1.0

    if cagr > 0.02:
        trend = "上升"
    elif cagr < -0.02:
        trend = "下降"
    else:
        trend = "持平"

    return CAGRResult(
        metric_name=metric_name,
        start_value=start_value,
        end_value=end_value,
        years=years,
        cagr=cagr,
        trend=trend,
    )


# ── 分位数 ──────────────────────────────────────────────────

def calculate_percentile(
    value: float,
    population: pd.Series | list[float],
    *,
    higher_is_better: bool = True,
) -> float:
    """计算给定值在群体中的分位数。

    Args:
        value: 目标值
        population: 群体数据
        higher_is_better: True → 越高越好（分位越高越好）

    Returns:
        分位数 (0.0 ~ 1.0)
    """
    if isinstance(population, list):
        population = pd.Series(population, dtype=float)

    population = population.dropna()
    if population.empty:
        return 0.5

    rank = (population < value).sum()
    percentile = rank / len(population)

    if not higher_is_better:
        percentile = 1.0 - percentile

    return percentile


def calculate_percentiles(
    values: dict[str, float],
    population_df: pd.DataFrame,
    *,
    higher_is_better: dict[str, bool] | None = None,
) -> dict[str, float]:
    """批量计算多个指标的分位数。

    Args:
        values: {指标名: 目标值}
        population_df: 群体数据 DataFrame (列名 = 指标名)
        higher_is_better: {指标名: 是否越高越好}，默认为 True

    Returns:
        {指标名: 分位数}
    """
    result = {}
    for metric, value in values.items():
        if metric not in population_df.columns:
            result[metric] = 0.5
            continue
        is_higher = True
        if higher_is_better:
            is_higher = higher_is_better.get(metric, True)
        result[metric] = calculate_percentile(
            value, population_df[metric], higher_is_better=is_higher
        )
    return result
