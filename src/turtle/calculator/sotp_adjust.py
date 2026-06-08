"""
SOTP 双口径调整 — 母公司可支配现金 vs 合并口径。

口径A: 母公司可支配现金 / 市值
口径B: 合并口径可支配现金 × 分红回流率 / 市值

|A - B| > 2pp → 需 Agent 综合判断（可能存在未分配利润沉淀在子公司）

设计哲学:
- 不替代 PR，只作为 PR 的补充验证
- 差异过大时标记为需人工/Agent 介入的疑点
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SOTPResult:
    """SOTP 双口径调整结果。"""
    ts_code: str
    method_a: float = 0.0          # 口径A: 母公司可支配/市值
    method_b: float = 0.0          # 口径B: 合并×回流率/市值
    abs_diff: float = 0.0          # |A - B|
    needs_agent_review: bool = False
    detail: str = ""

    # 组成项
    parent_disposable: float = 0.0    # 母公司可支配现金
    consolidated_disposable: float = 0.0  # 合并可支配现金
    repatriation_rate: float = 0.7    # 分红回流率 (默认70%)
    market_cap: float = 0.0           # 市值


class SOTPAdjuster:
    """SOTP 双口径调整器。

    用法:
        adj = SOTPAdjuster()
        result = adj.calculate(
            ts_code="600519.SH",
            parent_disposable=100e8,    # 母公司可支配现金
            consolidated_disposable=500e8,  # 合并可支配现金
            market_cap=2e12,            # 总市值
        )
        if result.needs_agent_review:
            print(f"SOTP 差异 {result.abs_diff:.1%}，需 Agent 介入")
    """

    # ── Thresholds ──
    DIFF_THRESHOLD: float = 0.02       # |A-B| > 2pp 触发 agent review
    DEFAULT_REPAT_RATE: float = 0.70   # 默认分红回流率 70%

    def calculate(
        self,
        ts_code: str,
        parent_disposable: float,
        consolidated_disposable: float,
        market_cap: float,
        *,
        repatriation_rate: float | None = None,
    ) -> SOTPResult:
        """计算 SOTP 双口径。

        Args:
            ts_code: 股票代码
            parent_disposable: 母公司可支配现金
            consolidated_disposable: 合并口径可支配现金
            market_cap: 年末总市值
            repatriation_rate: 分红回流率 (None → 使用默认 70%)
        """
        if market_cap <= 0:
            return SOTPResult(
                ts_code=ts_code,
                detail="市值无效，无法计算 SOTP",
            )

        rate = repatriation_rate if repatriation_rate is not None else self.DEFAULT_REPAT_RATE

        method_a = parent_disposable / market_cap
        method_b = consolidated_disposable * rate / market_cap
        abs_diff = abs(method_a - method_b)

        detail_parts = [
            f"口径A(母公司): {method_a:.2%} = {parent_disposable/1e8:.1f}亿 / {market_cap/1e8:.1f}亿",
            f"口径B(合并×{rate:.0%}): {method_b:.2%} = {consolidated_disposable/1e8:.1f}亿×{rate:.0%} / {market_cap/1e8:.1f}亿",
            f"差异: {abs_diff:.2%}",
        ]

        if abs_diff > self.DIFF_THRESHOLD:
            detail_parts.append(
                f"⚠️ |A-B| = {abs_diff:.2%} > {self.DIFF_THRESHOLD:.0%} 阈值，"
                f"可能存在子公司未分配利润沉淀，建议 Agent 综合判断"
            )

        return SOTPResult(
            ts_code=ts_code,
            method_a=method_a,
            method_b=method_b,
            abs_diff=abs_diff,
            needs_agent_review=abs_diff > self.DIFF_THRESHOLD,
            parent_disposable=parent_disposable,
            consolidated_disposable=consolidated_disposable,
            repatriation_rate=rate,
            market_cap=market_cap,
            detail="\n".join(detail_parts),
        )
