"""
回测统计分析 — win_rate / PR兑现率 / 分组spread / 跨窗口汇总。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.backtest.dividend_validator import DividendValidation


@dataclass
class GroupStats:
    """分组统计 (Top N vs Bottom N)。"""
    name: str
    count: int
    avg_pr: float = 0.0
    avg_fulfillment: float = 0.0  # 平均PR兑现率
    avg_dividend_yield: float = 0.0
    win_rate: float = 0.0  # 股息>无风险利率的比例
    avg_excess: float = 0.0


@dataclass
class WindowStats:
    """单窗口汇总统计。"""
    window_id: int
    window_label: str
    total_stocks: int
    avg_pr_pct: float = 0.0
    avg_fulfillment: float = 0.0
    win_rate: float = 0.0
    avg_excess: float = 0.0
    median_fulfillment: float = 0.0
    pr_qualified_pct: float = 0.0  # PR兑现率 >= 0.7 的比例

    # 分组对比
    top5_avg_dividend: float = 0.0
    bottom5_avg_dividend: float = 0.0
    spread: float = 0.0  # Top5 - Bottom5 股息差


class BacktestStatistics:
    """回测统计分析器。"""

    def analyze_window(
        self,
        validations: list[DividendValidation],
        window_id: int,
        window_label: str,
    ) -> WindowStats:
        """分析单个窗口的验证结果。"""
        valid = [v for v in validations if v.window_id == window_id]
        if not valid:
            return WindowStats(
                window_id=window_id, window_label=window_label, total_stocks=0,
            )

        prs = [v.predicted_pr_pct for v in valid]
        ffs = [v.pr_fulfillment for v in valid if v.pr_fulfillment > 0]
        exs = [v.excess for v in valid]
        divs = [v.actual_dividend_yield for v in valid if v.actual_dividend_yield > 0]

        # 按 FinalScore 排序分组
        sorted_stocks = sorted(valid, key=lambda v: v.final_score, reverse=True)
        top5 = sorted_stocks[:min(5, len(sorted_stocks))]
        bottom5 = sorted_stocks[-min(5, len(sorted_stocks)):]

        top5_div = float(np.mean([v.actual_dividend_yield for v in top5 if v.actual_dividend_yield > 0])) if top5 else 0
        bottom5_div = float(np.mean([v.actual_dividend_yield for v in bottom5 if v.actual_dividend_yield > 0])) if bottom5 else 0

        return WindowStats(
            window_id=window_id,
            window_label=window_label,
            total_stocks=len(valid),
            avg_pr_pct=round(float(np.mean(prs)), 2) if prs else 0,
            avg_fulfillment=round(float(np.mean(ffs)), 2) if ffs else 0,
            win_rate=round(sum(1 for v in valid if v.strategy_effective) / len(valid) * 100, 1) if valid else 0,
            avg_excess=round(float(np.mean(exs)), 2) if exs else 0,
            median_fulfillment=round(float(np.median(ffs)), 2) if ffs else 0,
            pr_qualified_pct=round(sum(1 for v in valid if v.pr_qualified) / len(valid) * 100, 1) if valid else 0,
            top5_avg_dividend=round(top5_div, 2),
            bottom5_avg_dividend=round(bottom5_div, 2),
            spread=round(top5_div - bottom5_div, 2),
        )

    def analyze_cross_window(self, window_stats_list: list[WindowStats]) -> GroupStats:
        """跨窗口汇总。"""
        all_win_rates = [s.win_rate for s in window_stats_list if s.total_stocks > 0]
        all_fulfillments = [s.avg_fulfillment for s in window_stats_list if s.total_stocks > 0]
        all_spreads = [s.spread for s in window_stats_list if s.total_stocks > 0]

        return GroupStats(
            name="跨窗口汇总",
            count=len(window_stats_list),
            win_rate=round(float(np.mean(all_win_rates)), 1) if all_win_rates else 0,
            avg_fulfillment=round(float(np.median(all_fulfillments)), 2) if all_fulfillments else 0,
            avg_excess=round(float(np.mean(all_spreads)), 2) if all_spreads else 0,
        )
