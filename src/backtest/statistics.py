"""
回测统计分析 — PR兑现率 / 阈值达标率 / 分组spread。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.backtest.dividend_validator import DividendValidation, PR_MIN_THRESHOLD


@dataclass
class WindowStats:
    """单窗口汇总统计。"""
    window_id: int
    window_label: str
    total_stocks: int

    # 核心指标
    avg_pr_pct: float = 0.0
    avg_fulfillment: float = 0.0       # 平均 PR 兑现率
    median_fulfillment: float = 0.0    # PR 兑现率中位数
    pr_fulfill_qualified_pct: float = 0.0  # 兑现率≥0.7 的比例

    # 阈值达标
    threshold_met_pct: float = 0.0     # 实际股息 ≥ 5% 的比例

    # 分组对比 (Top5 vs Bottom5)
    top5_avg_dividend: float = 0.0
    bottom5_avg_dividend: float = 0.0
    spread: float = 0.0               # Top-Bottom 股息差


@dataclass
class CrossWindowSummary:
    """跨窗口汇总。"""
    total_windows: int
    avg_fulfillment: float = 0.0       # 各窗口兑现率中位数的中位数
    avg_threshold_met_pct: float = 0.0 # 平均阈值达标率
    avg_spread: float = 0.0           # 平均 Top-Bottom 股息差
    has_discrimination: bool = False   # spread > 0 → 打分有区分度


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
            return WindowStats(window_id=window_id, window_label=window_label, total_stocks=0)

        prs = [v.predicted_pr_pct for v in valid]
        ffs = [v.pr_fulfillment for v in valid if v.pr_fulfillment > 0]

        # 兑现率
        avg_ff = round(float(np.mean(ffs)), 2) if ffs else 0
        med_ff = round(float(np.median(ffs)), 2) if ffs else 0
        ff_qualified = round(
            sum(1 for v in valid if v.is_pr_qualified) / len(valid) * 100, 1
        ) if valid else 0

        # 阈值达标率 (实际 ≥ 5%)
        threshold_met = round(
            sum(1 for v in valid if v.pr_threshold_met) / len(valid) * 100, 1
        ) if valid else 0

        # 分组对比
        sorted_stocks = sorted(valid, key=lambda v: v.final_score, reverse=True)
        top5 = sorted_stocks[:min(5, len(sorted_stocks))]
        bottom5 = sorted_stocks[-min(5, len(sorted_stocks)):]

        top5_div_pcts = [v.actual_dividend_yield for v in top5 if v.actual_dividend_yield > 0]
        bottom5_div_pcts = [v.actual_dividend_yield for v in bottom5 if v.actual_dividend_yield > 0]

        top5_avg = round(float(np.mean(top5_div_pcts)), 2) if top5_div_pcts else 0
        bottom5_avg = round(float(np.mean(bottom5_div_pcts)), 2) if bottom5_div_pcts else 0

        return WindowStats(
            window_id=window_id,
            window_label=window_label,
            total_stocks=len(valid),
            avg_pr_pct=round(float(np.mean(prs)), 1) if prs else 0,
            avg_fulfillment=avg_ff,
            median_fulfillment=med_ff,
            pr_fulfill_qualified_pct=ff_qualified,
            threshold_met_pct=threshold_met,
            top5_avg_dividend=top5_avg,
            bottom5_avg_dividend=bottom5_avg,
            spread=round(top5_avg - bottom5_avg, 2),
        )

    def analyze_cross_window(self, window_stats_list: list[WindowStats]) -> CrossWindowSummary:
        """跨窗口汇总。"""
        valid = [s for s in window_stats_list if s.total_stocks > 0]
        if not valid:
            return CrossWindowSummary(total_windows=0)

        ffs = [s.median_fulfillment for s in valid]
        thresh = [s.threshold_met_pct for s in valid]
        spreads = [s.spread for s in valid]

        return CrossWindowSummary(
            total_windows=len(valid),
            avg_fulfillment=round(float(np.median(ffs)), 2) if ffs else 0,
            avg_threshold_met_pct=round(float(np.mean(thresh)), 1) if thresh else 0,
            avg_spread=round(float(np.mean(spreads)), 2) if spreads else 0,
            has_discrimination=all(s > 0 for s in spreads) if spreads else False,
        )
