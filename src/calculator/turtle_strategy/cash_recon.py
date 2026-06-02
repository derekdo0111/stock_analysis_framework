"""
OE 质量四级验证 — 含金量 / 稳定性 / 趋势 / BS 一致性。

验证 OE_cf 是否可靠，产出三级标签:
- 🟢 可信: 全部通过
- 🟡 存疑: 部分不通过 → L4 × 0.7
- 🔴 不可靠: 关键项不通过 → L4 = 0

设计哲学:
- 不直接修改 OE 数值，只产出质量标签
- 标签前置生效于 PR 计算之前
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger

from src.calculator.turtle_strategy.oe_calculator import OECalculationResult


@dataclass
class CashReconCheck:
    """单项验证结果。"""
    name: str
    passed: bool
    score: float = 0.0        # 该项得分 (0~1)
    detail: str = ""
    threshold_used: float = 0.0
    actual_value: float = 0.0


@dataclass
class CashReconResult:
    """OE 质量四级验证完整结果。"""
    ts_code: str
    label: str = ""              # "🟢可信" / "🟡存疑" / "🔴不可靠"
    multiplier: float = 1.0      # 1.0 / 0.7 / 0.0
    checks: list[CashReconCheck] = field(default_factory=list)
    total_score: float = 0.0     # 四级总分
    max_score: float = 4.0       # 满分

    @property
    def is_reliable(self) -> bool:
        return self.label == "可信"


class CashRecon:
    """OE 质量四级验证器。

    四级:
    1. 含金量: OE_cf / 净利润 (验证现金流真实性)
    2. 稳定性: OE_cf 变异系数 CV (验证稳定性)
    3. 趋势: OE_cf 3年 CAGR (验证增长趋势)
    4. BS 一致性: 应收/存货增速 vs 营收增速 (验证资产负债表)
    """

    # ── Thresholds ──
    GOLD_RATIO_MIN: float = 0.7       # OE_cf/净利润 最低含金量
    STABILITY_CV_MAX: float = 0.5     # CV 上限
    TREND_CAGR_MIN: float = -0.10     # 3年 CAGR 下限
    BS_DEVIATION_MAX: float = 0.20    # 应收/营收增速偏差上限

    def __init__(self, oe_result: OECalculationResult):
        self._oe = oe_result

    def run(self) -> CashReconResult:
        """执行完整四级验证。"""
        checks: list[CashReconCheck] = []

        # Level 1: 含金量
        c1 = self._check_gold_content()
        checks.append(c1)

        # Level 2: 稳定性
        c2 = self._check_stability()
        checks.append(c2)

        # Level 3: 趋势
        c3 = self._check_trend()
        checks.append(c3)

        # Level 4: BS 一致性 (需要额外数据，有则做无则跳过)
        c4 = self._check_bs_consistency()
        if c4:
            checks.append(c4)

        # 汇总
        total = sum(c.score for c in checks)
        max_score = len(checks)

        # 三级标签判定
        fail_count = sum(1 for c in checks if not c.passed)
        label: str
        multiplier: float

        if fail_count == 0:
            label = "可信"
            multiplier = 1.0
        elif fail_count <= 1 and total >= max_score * 0.5:
            label = "存疑"
            multiplier = 0.7
        else:
            label = "不可靠"
            multiplier = 0.0

        return CashReconResult(
            ts_code=self._oe.ts_code,
            label=label,
            multiplier=multiplier,
            checks=checks,
            total_score=total,
            max_score=float(max_score),
        )

    # ── Individual checks ──────────────────────────────────

    def _check_gold_content(self) -> CashReconCheck:
        """Level 1: OE_cf / 净利润 ≥ 0.7 → 现金流含金量充足。"""
        oe_cf_vals = self._oe.oe_cf_values
        if not oe_cf_vals or self._oe.net_profit_median <= 0:
            return CashReconCheck(
                name="含金量",
                passed=False,
                score=0.0,
                detail="缺少 OE_cf 或净利润数据",
            )

        median_oe = np.median(oe_cf_vals)
        ratio = median_oe / self._oe.net_profit_median if self._oe.net_profit_median else 0
        passed = ratio >= self.GOLD_RATIO_MIN

        return CashReconCheck(
            name="含金量",
            passed=passed,
            score=1.0 if passed else 0.0,
            detail=f"OE_cf中位数/净利润中位数 = {ratio:.2f} (阈值 {self.GOLD_RATIO_MIN})",
            threshold_used=self.GOLD_RATIO_MIN,
            actual_value=ratio,
        )

    def _check_stability(self) -> CashReconCheck:
        """Level 2: OE_cf CV ≤ 0.5 → 现金流稳定。"""
        oe_cf_vals = [v for v in self._oe.oe_cf_values if v != 0]
        if len(oe_cf_vals) < 3:
            return CashReconCheck(
                name="稳定性",
                passed=False,
                score=0.0,
                detail=f"数据不足 ({len(oe_cf_vals)} 年)",
            )

        mean_val = np.mean(oe_cf_vals)
        std_val = np.std(oe_cf_vals)
        cv = std_val / abs(mean_val) if mean_val else float("inf")
        passed = cv <= self.STABILITY_CV_MAX

        return CashReconCheck(
            name="稳定性",
            passed=passed,
            score=1.0 if passed else 0.0,
            detail=f"CV = {cv:.3f} (阈值 {self.STABILITY_CV_MAX})",
            threshold_used=self.STABILITY_CV_MAX,
            actual_value=cv,
        )

    def _check_trend(self) -> CashReconCheck:
        """Level 3: OE_cf 3年 CAGR ≥ -10% → 趋势不恶化。"""
        oe_cf_vals = list(self._oe.oe_cf_values)
        if len(oe_cf_vals) < 4:
            return CashReconCheck(
                name="趋势",
                passed=False,
                score=0.0,
                detail=f"需要 ≥4 年数据，当前 {len(oe_cf_vals)} 年",
            )

        # 取近3年
        recent = oe_cf_vals[-3:]
        if recent[0] <= 0:
            return CashReconCheck(
                name="趋势",
                passed=False,
                score=0.0,
                detail="起始值非正，无法计算 CAGR",
            )

        cagr = (recent[-1] / recent[0]) ** (1.0 / 2.0) - 1.0
        passed = cagr >= self.TREND_CAGR_MIN

        return CashReconCheck(
            name="趋势",
            passed=passed,
            score=1.0 if passed else 0.0,
            detail=f"3年 CAGR = {cagr:.1%} (阈值 {self.TREND_CAGR_MIN:.0%})",
            threshold_used=self.TREND_CAGR_MIN,
            actual_value=cagr,
        )

    def _check_bs_consistency(self) -> CashReconCheck | None:
        """Level 4: 应收增速 vs 营收增速 偏差 ≤ 20%。

        需要 BS 数据，当前版本暂用 OE 路径A vs 路径B 差异替代。
        """
        # 使用利润→现金转化率作为 BS 一致性的代理
        if not self._oe.path_a_values or not self._oe.oe_cf_values:
            return None

        n = min(len(self._oe.path_a_values), len(self._oe.oe_cf_values))
        if n < 3:
            return None

        # 路径A(利润视角) vs 路径B(现金视角) 的中位数比值
        pa_median = np.median(self._oe.path_a_values[-n:])
        pb_median = np.median(self._oe.oe_cf_values[-n:])

        if pa_median == 0:
            return None

        conversion_ratio = pb_median / pa_median
        # 理想: 现金 ≈ 利润 (ratio ≈ 1.0)
        deviation = abs(conversion_ratio - 1.0)
        passed = deviation <= self.BS_DEVIATION_MAX

        return CashReconCheck(
            name="利润→现金转化率",
            passed=passed,
            score=1.0 if passed else 0.0,
            detail=f"OE_cf/OE_income = {conversion_ratio:.2f} (偏差 {deviation:.1%}, 阈值 {self.BS_DEVIATION_MAX:.0%})",
            threshold_used=self.BS_DEVIATION_MAX,
            actual_value=deviation,
        )
