"""
加法打分模型 v0.23 — Final = L3_30pt + L4_45pt + L5_25pt = 100pt。

管线:
  L1 HardGate (不评分) → L2 初筛门控 (不评分) → 公司分类 →
  L3 商业模式 (0-30pt) + L4 穿透回报率 (0-45pt) + L5 安全边际 (0-25pt) = 100pt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.data.pool.bundle import StockDataBundle
from src.turtle.calculator.pr_calculator import PRCalculator
from src.turtle.calculator.l3_calculator import L3Calculator, L3Result
from src.turtle.calculator.l5_calculator import L5Calculator, L5Result
from src.turtle.screening.l2_screener import L2Screener
from src.turtle.screening.hard_gate import HardGateChecker
from src.turtle.screening.classifier import CompanyClassifier
from src.turtle.rules.loader import load_rules


# v0.23: L4 内部满分 40，输出缩放到 45
L4_SCALE = 45.0 / 40.0


@dataclass
class FinalScore:
    """最终评分输出 — v0.23 加法百分制。"""

    ts_code: str
    name: str = ""

    # ── 各层得分 (百分制) ──
    l2_score: float = 0.0       # v0.23: 仅显示，不参与最终计算
    l3_score: float = 0.0       # 0-30 商业模式
    l4_score: float = 0.0       # 0-45 穿透回报率 (已缩放)
    l5_score: float = 0.0       # 0-25 安全边际

    # ── 最终得分 ──
    final_score: float = 0.0    # v0.23: = L3 + L4 + L5

    # ── 归属池 ──
    pool: str = "备选池"

    # ── L3 详情 ──
    l3_dim_scores: dict = field(default_factory=dict)  # dim_id → {score, label, name, group}
    l3_level: str = ""                                  # 优/良/中/差
    l3_total_dim: float = 0.0                           # 0-24
    l3_group_scores: dict = field(default_factory=dict)

    # ── L4 PR 详情 ──
    pr_pct: float = 0.0
    pr_disposable_cash: float = 0.0
    pr_distribution_ratio: float = 0.0
    pr_distribution_source: str = ""
    pr_buyback_cancellation: float = 0.0
    oe_quality: str = ""

    # ── L5 详情 ──
    l5_safety_margin_pct: float = 0.0
    l5_reasonable_mv: float = 0.0
    l5_valuation_score: float = 0.0
    l5_downside_score: float = 0.0
    l5_downside_details: list = field(default_factory=list)
    position_pct: float = 0.0
    l5_position_score: float = 0.0

    # ── 状态 ──
    is_valid: bool = True
    skip_reason: str = ""

    # ── 中间结果 ──
    hard_gate_passed: bool = True
    hard_gate_checks: list[dict[str, Any]] = field(default_factory=list)

    l2_details: dict[str, float] = field(default_factory=dict)
    l2_pool: str = ""

    classify_type: str = ""
    classify_reason: str = ""

    oe_cf_median: float = 0.0
    oe_cf_mean: float = 0.0
    oe_cv: float = 0.0
    oe_cagr: float = 0.0
    oe_path_b_values: list[float] = field(default_factory=list)
    pr_starting_score: float = 0.0
    pr_quality_penalty: float = 0.0
    capex_coefficient: float = 0.0
    oe_to_profit_ratio: float = 0.0       # v0.33: OE_cf/净利润 中位数比
    bs_unexplained_diff_pct: float = 0.0  # v0.33: BS一致性差异%

    # ── v0.34: L3 后修正 ──
    management_stability_adjusted: bool = False  # Phase 3.5 LLM 后是否已修正管理层稳定性

    def adjust_management_stability(self, new_score: int, label: str = "") -> None:
        """Phase 3.5 后修正 L3 管理层稳定性维度得分。

        仅修正 management_stability 单一维度，重新计算 L3 总分和 Final。

        Args:
            new_score: 新得分 (0, 1, 或 2)
            label: 新标签 (如 "管理层稳定（LLM 确认）")
        """
        dim_id = "management_stability"
        old_info = self.l3_dim_scores.get(dim_id)
        if old_info is None:
            return

        old_score = old_info.get("score", 1)
        if old_score == new_score:
            return  # 无需修正

        delta = new_score - old_score

        # 更新维度详情
        old_info["score"] = new_score
        old_info["label"] = label or (
            "管理层稳定（LLM 确认）" if new_score == 2
            else "管理层频繁变更（LLM 检出）" if new_score == 0
            else "数据不足（默认中性）"
        )

        # 更新 L3 总分
        self.l3_total_dim = round(self.l3_total_dim + delta, 1)
        self.l3_score = round(min(30.0, self.l3_total_dim / 24.0 * 30.0), 2)

        # 更新分组汇总
        if "治理" in self.l3_group_scores:
            self.l3_group_scores["治理"]["score"] = (
                self.l3_group_scores["治理"].get("score", 0) + delta
            )

        # 重新计算 Final
        self.final_score = round(self.l3_score + self.l4_score + self.l5_score, 2)

        # 重新分池
        if self.final_score >= 75:
            self.pool = "核心池"
        elif self.final_score >= 50:
            self.pool = "观察池"
        else:
            self.pool = "备选池"

        self.management_stability_adjusted = True


class TurtleScorer:
    """龟龟策略完整打分器 — v0.23 加法百分制。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._l2 = L2Screener(bundle)
        self._classifier = CompanyClassifier(bundle)
        self._hard_gate = HardGateChecker(bundle)
        self._pr = PRCalculator(bundle)
        self._l3 = L3Calculator(bundle)
        self._l5 = L5Calculator(bundle)
        self._rules = load_rules()
        self._scoring = self._rules.turtle_constants.scoring

    def score(self, ts_code: str) -> FinalScore:
        """跑完整打分管线 — v0.23。"""
        result = FinalScore(ts_code=ts_code)

        # ── 获取基础信息 ──
        result.name = self._bundle.name
        industry = self._bundle.industry

        # ═══════════════════════════════════════════
        # L1: HardGate 否决
        # ═══════════════════════════════════════════
        hg = self._hard_gate.check(ts_code)
        result.hard_gate_passed = hg.passed
        if hg.details:
            result.hard_gate_checks = []
            for k, v in hg.details.items():
                result.hard_gate_checks.append({
                    "name": k,
                    "passed": not hg.veto_reason or k not in str(hg.veto_reason),
                    "value": str(v),
                })
            if hg.veto_reason:
                for c in result.hard_gate_checks:
                    if c["name"] in hg.veto_reason or hg.veto_reason in c["name"]:
                        c["passed"] = False
                        break
        if not hg.passed:
            result.is_valid = False
            result.skip_reason = f"HardGate否决: {hg.veto_reason}"
            return result

        # ═══════════════════════════════════════════
        # L2: 初筛门控 (不参与最终评分)
        # ═══════════════════════════════════════════
        l2 = self._l2.score(ts_code, result.name)
        if l2.eliminated:
            result.is_valid = False
            result.skip_reason = f"L2淘汰: {l2.eliminate_reason}"
            return result

        # v0.23: L2 仅保留门控功能，分数仅用于展示
        result.l2_score = round(l2.total, 1)
        result.l2_details = {
            "financial_quality": l2.financial_quality,
            "valuation": l2.valuation,
            "liquidity": l2.liquidity,
            "bonus": l2.bonus,
        }
        result.l2_pool = l2.pool

        # ═══════════════════════════════════════════
        # 公司分类
        # ═══════════════════════════════════════════
        cls = self._classifier.classify(ts_code)
        result.classify_type = cls.category
        result.classify_reason = getattr(cls, 'reason', '')
        if not cls.eligible:
            result.is_valid = False
            result.skip_reason = f"分类排除({cls.category}): {result.classify_reason}"
            return result

        # ═══════════════════════════════════════════
        # L3: 商业模式十二维评估 (0-30pt)
        # ═══════════════════════════════════════════
        l3_result = self._l3.calculate(ts_code)
        result.l3_score = l3_result.l3_score
        result.l3_level = l3_result.level
        result.l3_total_dim = l3_result.total_dim_score
        result.l3_dim_scores = l3_result.dim_scores
        result.l3_group_scores = l3_result.group_scores

        # ═══════════════════════════════════════════
        # L4: 穿透回报率 (内部满分40, 缩放至45)
        # ═══════════════════════════════════════════
        pr = self._pr.calculate(ts_code, industry)
        result.l4_score = round(pr.l4_score * L4_SCALE, 2)
        result.pr_pct = pr.pr_pct
        result.pr_disposable_cash = pr.disposable_cash
        result.pr_distribution_ratio = pr.distribution_ratio
        result.pr_distribution_source = pr.distribution_source
        result.pr_buyback_cancellation = pr.buyback_cancellation
        result.oe_quality = pr.oe_quality_label
        result.pr_starting_score = pr.starting_score
        result.pr_quality_penalty = pr.quality_penalty
        result.oe_cf_median = pr.oe_cf_median
        result.oe_cf_mean = pr.oe_cf_mean
        result.oe_cv = pr.oe_cv
        result.oe_cagr = pr.oe_cagr
        result.oe_path_b_values = list(pr.oe_path_b_values) if pr.oe_path_b_values else []
        result.capex_coefficient = pr.capex_coefficient
        result.oe_to_profit_ratio = pr.oe_to_profit_ratio
        result.bs_unexplained_diff_pct = pr.bs_unexplained_diff_pct
        if not pr.is_valid:
            result.l4_score = 0.0

        # ═══════════════════════════════════════════
        # L5: 估值安全边际 (0-25pt)
        # ═══════════════════════════════════════════
        l5_result = self._l5.calculate(ts_code, industry)
        result.l5_score = l5_result.l5_score
        result.l5_safety_margin_pct = l5_result.safety_margin_pct
        result.l5_reasonable_mv = l5_result.reasonable_market_cap
        result.l5_valuation_score = l5_result.valuation_score
        result.l5_downside_score = l5_result.downside_buffer_score
        result.l5_downside_details = l5_result.downside_buffer_details
        result.position_pct = l5_result.position_pct
        result.l5_position_score = l5_result.position_score

        # ═══════════════════════════════════════════
        # Final = L3 + L4 + L5 (0-100pt)
        # ═══════════════════════════════════════════
        result.final_score = round(result.l3_score + result.l4_score + result.l5_score, 2)

        # ── 分池 ──
        pools = self._scoring.pools
        if result.final_score >= pools.core:
            result.pool = "核心池"
        elif result.final_score >= pools.watch:
            result.pool = "观察池"
        else:
            result.pool = "备选池"

        return result


# ── 快捷函数 ──

def quick_score(ts_code: str, token: str | None = None) -> FinalScore:
    """快捷打分 — 一行代码跑完整管线。"""
    from src.core.data.tushare_client import TushareClient
    from src.core.data.orchestrator import DataPoolOrchestrator
    client = TushareClient(token=token)
    orch = DataPoolOrchestrator(client)
    orch.snapshot_stock(ts_code)
    bundle = orch.get_bundle(ts_code)
    if bundle is None:
        raise RuntimeError(f"快照失败: {ts_code}")
    scorer = TurtleScorer(bundle)
    return scorer.score(ts_code)
