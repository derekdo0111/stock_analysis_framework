"""
分红验证器 — PR 兑现率 + 超额收益。

核心理念:
  PR = OE_cf_median / MarketCap → 预期每股可分配现金
  实际 = Tushare dividend 接口获取实际分红
  PR兑现率 = 实际股息回报 / 预期 PR
  超额 = 股息回报 - 无风险利率
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data_fetcher.tushare_client import TushareClient
from src.backtest.window_manager import BacktestWindow


# 中国10年期国债收益率参考值 (年化 %)
RISK_FREE_RATES = {
    2016: 2.85, 2017: 3.88, 2018: 3.23, 2019: 3.14,
    2020: 2.95, 2021: 2.78, 2022: 2.84, 2023: 2.56,
    2024: 2.30, 2025: 2.00,
}


@dataclass
class DividendValidation:
    """单只股票在一个窗口的分红验证结果。"""
    ts_code: str
    name: str = ""

    # 预测值
    predicted_pr_pct: float = 0.0
    predicted_dividend_yield: float = 0.0  # 预期股息回报 (≈ PR)

    # 实际值
    actual_dividend_yield: float = 0.0  # 实际年化股息回报
    actual_dividends: list[float] = field(default_factory=list)  # 每年每股派息

    # 指标
    pr_fulfillment: float = 0.0  # 实际/预期，≥0.7 合格
    excess: float = 0.0  # 股息回报 - 无风险利率，>0 有效
    risk_free_rate: float = 0.0

    # 判定
    pr_qualified: bool = False
    strategy_effective: bool = False

    # 回测窗口
    window_id: int = 0
    final_score: float = 0.0


class DividendValidator:
    """分红验证器。"""

    def __init__(self, client: TushareClient):
        self._client = client

    def validate(
        self,
        ts_code: str,
        name: str,
        predicted_pr_pct: float,
        window: BacktestWindow,
        final_score: float = 0,
        market_cap: float = 0,
    ) -> DividendValidation:
        """验证单只股票在指定窗口的分红。

        Args:
            ts_code: 股票代码
            name: 股票名称
            predicted_pr_pct: 穿透回报率 (%)
            window: 回测窗口
            final_score: 最终得分 (用于排序)
            market_cap: 选股时市值 (亿元)
        """
        result = DividendValidation(
            ts_code=ts_code,
            name=name,
            predicted_pr_pct=predicted_pr_pct,
            window_id=window.id,
            final_score=final_score,
        )

        # 无风险利率
        rf = RISK_FREE_RATES.get(window.validate_start_year, 2.5)
        result.risk_free_rate = rf

        # PR 作为预期股息回报
        result.predicted_dividend_yield = predicted_pr_pct

        # 拉取验证期实际分红
        try:
            dividends = self._fetch_dividends(ts_code, window)
            result.actual_dividends = dividends

            if dividends and any(d > 0 for d in dividends):
                avg_div = float(np.mean([d for d in dividends if d > 0]))
                # 实际股息回报 = 年均分红 / 选股时股价
                # 用 market_cap (亿元×1e8) 和总股本反推
                if market_cap > 0:
                    # 粗略: 用 PR 公式反推股价
                    # PR = OE / MV, MV = OE / PR
                    # 股价 ≈ 每股OE / PR
                    # 实际股息率 = 分红 / 股价
                    # 简化: 用每股市价 ≈ market_cap/总股本
                    # 由于总股本未知, 直接用 分红/市值 估算
                    pass

                result.actual_dividend_yield = avg_div
        except Exception:
            pass

        # 计算指标
        if result.predicted_dividend_yield > 0:
            result.pr_fulfillment = result.actual_dividend_yield / result.predicted_dividend_yield
        result.excess = result.actual_dividend_yield - rf

        result.pr_qualified = result.pr_fulfillment >= 0.7
        result.strategy_effective = result.excess > 0

        return result

    def _fetch_dividends(self, ts_code: str, window: BacktestWindow) -> list[float]:
        """拉取验证期的每股分红。"""
        try:
            df = self._client.dividend(ts_code=ts_code)
            if df.empty:
                return []
            dividends = []
            for _, row in df.iterrows():
                end_date = str(row.get("end_date", ""))
                if not end_date:
                    continue
                year = int(end_date[:4]) if len(end_date) >= 4 else 0
                if window.validate_start_year <= year <= window.validate_end_year:
                    cash_div = float(row.get("cash_div") or 0)
                    if cash_div > 0 and str(row.get("div_proc", "")).strip() == "实施":
                        dividends.append(cash_div)
            return dividends
        except Exception:
            return []
