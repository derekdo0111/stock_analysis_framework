"""
龟龟策略专用常数 — 从 turtle_constants.yaml 加载并暴露为 Python 常量。

所有阈值/权重/系数均从 YAML 加载，代码不做硬编码。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.rules.loader import load_rules


@dataclass
class TurtleConstants:
    """龟龟策略全部常数的内存缓存。

    从 turtle_constants.yaml 一次加载，零散访问。
    """

    # ── OE ──
    oe_capex_prior_weight: float = 0.4
    oe_asset_intensity_weight: float = 0.6

    # ── PR ──
    pr_threshold_top: float = 0.12     # >= 12% → 20分
    pr_threshold_mid: float = 0.08     # >= 8% → 15分
    pr_threshold_low: float = 0.05     # >= 5% → 10分, < 5% → 0分
    pr_score_top: float = 20.0
    pr_score_mid: float = 15.0
    pr_score_low: float = 10.0
    pr_score_bottom: float = 0.0
    pr_max_score: float = 40.0         # L4 上限

    # ── L5 ──
    l5_max_score: float = 25.0         # L5 上限
    l5_extrapolation_max: float = 30.0  # 外推可行度满分
    l5_trap_max: float = 7.0           # 价值陷阱最多扣分

    # ── L3 ──
    l3_excellent: float = 1.2
    l3_good: float = 1.0
    l3_medium: float = 0.8

    # ── Pool thresholds ──
    pool_core: float = 75.0
    pool_observe: float = 55.0

    # ── Raw config (for advanced usage) ──
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls) -> TurtleConstants:
        """从 turtle_constants.yaml 加载所有常数。"""
        rules = load_rules()
        tc = rules.turtle_constants
        inst = cls(raw=tc.model_dump() if tc else {})

        if tc is None:
            return inst

        # OE
        oe = tc.owners_earnings
        if oe and oe.maintenance_capex_coefficient:
            inst.oe_capex_prior_weight = oe.maintenance_capex_coefficient.prior_weight
            inst.oe_asset_intensity_weight = oe.maintenance_capex_coefficient.asset_intensity_weight

        # PR thresholds
        pr = tc.penetration_return
        if pr and pr.thresholds:
            for t in pr.thresholds:
                if t.score >= inst.pr_score_top:
                    inst.pr_threshold_top = t.min_return
                elif t.score >= inst.pr_score_mid:
                    inst.pr_threshold_mid = t.min_return
                elif t.score > 0:
                    inst.pr_threshold_low = t.min_return

        if pr and pr.max_score:
            inst.pr_max_score = pr.max_score

        # L5
        l5 = tc.margin_safety
        if l5:
            if l5.max_score:
                inst.l5_max_score = l5.max_score
            if l5.extrapolation:
                inst.l5_extrapolation_max = getattr(l5.extrapolation, 'max_score', 30.0)
            if l5.value_trap:
                inst.l5_trap_max = getattr(l5.value_trap, 'max_penalty', 7.0)

        # L3
        l3 = tc.l3_multiplier
        if l3:
            inst.l3_excellent = getattr(l3, 'excellent', 1.2)
            inst.l3_good = getattr(l3, 'good', 1.0)
            inst.l3_medium = getattr(l3, 'medium', 0.8)

        return inst


# ── Module-level singleton ──────────────────────────────────
_constants: TurtleConstants | None = None


def get_constants() -> TurtleConstants:
    """获取龟龟常数单例。"""
    global _constants
    if _constants is None:
        _constants = TurtleConstants.from_yaml()
    return _constants
