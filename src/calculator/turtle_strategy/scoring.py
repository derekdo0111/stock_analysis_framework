"""
乘法打分模型 Final = (L2 + L4 + L5) × L3。

输入:
- L2: 20pt (L2初筛)
- L4: 40pt (穿透回报率)
- L5: 25pt (安全边际)
- L3: ×1.2/×1.0/×0.8/reject

输出:
- raw_total = L2 + L4 + L5
- final = raw_total × L3
- pool: ≥75核心池 / 55~74观察池 / <55备选池
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.data_pool.bundle import StockDataBundle
from src.calculator.turtle_strategy.pr_calculator import PRCalculator
from src.calculator.turtle_strategy.l5_calculator import L5Calculator
from src.screener.l2_screener import L2Screener
from src.screener.hard_gate import HardGateChecker
from src.screener.classifier import CompanyClassifier
from src.rules.loader import load_rules


@dataclass
class FinalScore:
    """最终评分输出 — 包含完整管线中间结果。"""
    ts_code: str
    name: str = ""

    # 各层得分
    l2_score: float = 0.0
    l3_multiplier: float = 1.0
    l4_score: float = 0.0
    l5_score: float = 0.0

    # 最终得分
    raw_total: float = 0.0
    final_score: float = 0.0

    # 归属池
    pool: str = "备选池"

    # PR 详情 (v0.19)
    pr_pct: float = 0.0
    pr_disposable_cash: float = 0.0
    pr_distribution_ratio: float = 0.0
    pr_distribution_source: str = ""
    pr_buyback_cancellation: float = 0.0
    oe_quality: str = ""

    # 商业模式
    business_model: str = "良"

    # 仓位
    position_pct: float = 0.0

    # 状态
    is_valid: bool = True
    skip_reason: str = ""

    # ── 中间结果（富数据） ──
    hard_gate_passed: bool = True
    hard_gate_checks: list[dict[str, Any]] = field(default_factory=list)

    l2_details: dict[str, float] = field(default_factory=dict)  # financial_quality, valuation, etc.
    l2_pool: str = ""

    classify_type: str = ""
    classify_reason: str = ""

    oe_cf_median: float = 0.0
    oe_cf_mean: float = 0.0
    oe_cv: float = 0.0
    oe_cagr: float = 0.0
    oe_path_b_values: list[float] = field(default_factory=list)
    capex_coefficient: float = 0.0
    capex_industry_prior: float = 0.0
    capex_asset_score: float = 0.0

    pr_starting_score: float = 0.0
    pr_quality_penalty: float = 0.0

    l5_extrapolation_dims: dict[str, float] = field(default_factory=dict)
    l5_extrapolation_total: float = 0.0
    l5_extrapolation_level: str = ""
    l5_traps_triggered: list[str] = field(default_factory=list)
    l5_trap_score: int = 0
    l5_trap_level: str = ""
    l5_position_label: str = ""


class TurtleScorer:
    """龟龟策略完整打分器 — 串联全部计算模块。所有数据从 StockDataBundle 读取。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._l2 = L2Screener(bundle)
        self._classifier = CompanyClassifier(bundle)
        self._hard_gate = HardGateChecker(bundle)
        self._pr = PRCalculator(bundle)
        self._l5 = L5Calculator(bundle)
        self._rules = load_rules()
        self._scoring = self._rules.turtle_constants.scoring
        self._l3_cfg = self._rules.turtle_constants.business_model_multiplier

    def score(self, ts_code: str) -> FinalScore:
        """跑完整打分管线，捕获全部中间结果。"""
        result = FinalScore(ts_code=ts_code)

        # ── 获取基础信息（从 bundle） ──
        result.name = self._bundle.name
        industry = self._bundle.industry

        # ── HardGate ──
        hg = self._hard_gate.check(ts_code)
        result.hard_gate_passed = hg.passed
        if hg.details:
            result.hard_gate_checks = []
            for k, v in hg.details.items():
                # v may be str/int/float — all are display values
                result.hard_gate_checks.append({
                    "name": k,
                    "passed": not hg.veto_reason or k not in str(hg.veto_reason),
                    "value": str(v),
                })
            # Mark the actual veto item
            if hg.veto_reason:
                for c in result.hard_gate_checks:
                    if c["name"] in hg.veto_reason or hg.veto_reason in c["name"]:
                        c["passed"] = False
                        break
            # If all passed but veto_reason exists, mark first as failed
            if hg.veto_reason and all(c["passed"] for c in result.hard_gate_checks):
                pass  # veto_reason may not match detail keys exactly
        if not hg.passed:
            result.is_valid = False
            result.skip_reason = f"HardGate否决: {hg.veto_reason}"
            return result

        # ── L2 ──
        l2 = self._l2.score(ts_code, result.name)
        if l2.eliminated:
            result.is_valid = False
            result.skip_reason = f"L2淘汰: {l2.eliminate_reason}"
            return result
        result.l2_score = l2.total
        result.l2_details = {
            "financial_quality": l2.financial_quality,
            "valuation": l2.valuation,
            "liquidity": l2.liquidity,
            "bonus": l2.bonus,
        }
        result.l2_pool = l2.pool

        # ── 公司分类 ──
        cls = self._classifier.classify(ts_code)
        result.classify_type = cls.category
        result.classify_reason = getattr(cls, 'reason', '')
        if not cls.eligible:
            result.is_valid = False
            result.skip_reason = f"分类排除({cls.category}): {result.classify_reason}"
            return result

        # ── L3 商业模式乘数 ──
        result.l3_multiplier = self._estimate_l3(ts_code, industry)
        if result.l3_multiplier == -1:
            result.is_valid = False
            result.skip_reason = "商业模式判'差'，不进入最终评分"
            return result

        # ── L4 穿透回报率 (v0.19) ──
        pr = self._pr.calculate(ts_code, industry)
        result.l4_score = pr.l4_score
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
        if not pr.is_valid:
            result.l4_score = 0.0

        # ── L5 安全边际 ──
        l5 = self._l5.calculate(ts_code, industry)
        result.l5_score = l5.l5_score
        result.position_pct = l5.position_pct
        result.l5_extrapolation_dims = l5.extrapolation_dims
        result.l5_extrapolation_total = l5.extrapolation_total
        result.l5_extrapolation_level = l5.extrapolation_level
        result.l5_traps_triggered = l5.traps_triggered
        result.l5_trap_score = l5.trap_score
        result.l5_trap_level = l5.trap_level
        result.l5_position_label = l5.position_label

        # ── 乘法打分 ──
        result.raw_total = round(result.l2_score + result.l4_score + result.l5_score, 2)
        result.final_score = round(result.raw_total * result.l3_multiplier, 2)

        # ── 分池 ──
        pools = self._scoring.pools
        if result.final_score >= pools.core:
            result.pool = "核心池"
        elif result.final_score >= pools.watch:
            result.pool = "观察池"
        else:
            result.pool = "备选池"

        return result

    def _estimate_l3(self, ts_code: str, industry: str) -> float:
        """估算 L3 商业模式乘数。

        基于: ROE水平 + 毛利率 + 行业地位

        v0.19 fix: 优先取年报ROE；若无年报则基于季报推测全年ROE。
        Tushare fina_indicator 的 roe 字段为累计值（非年化），
        Q1→×4, H1→×2, Q3→×4/3。
        """
        try:
            fi = self._bundle.fina_indicator
            if fi.empty:
                return self._l3_cfg.good

            # ── 优先取最近年报 ──
            annual = fi[
                fi["end_date"].astype(str).str[-4:] == "1231"
            ].head(1)

            if not annual.empty:
                roe = annual.iloc[0].get("roe") or 0
                gm = annual.iloc[0].get("grossprofit_margin") or 0
            else:
                # ── 无年报：用最近季报推测全年ROE ──
                latest = fi.head(1)
                roe_raw = latest.iloc[0].get("roe") or 0
                gm = latest.iloc[0].get("grossprofit_margin") or 0

                try:
                    end_str = str(latest.iloc[0].get("end_date", "")).strip()
                    month = int(end_str[4:6]) if len(end_str) >= 6 else 12
                except (ValueError, IndexError):
                    month = 12

                if month == 12:
                    roe = roe_raw                    # 年报，直接用
                elif month in (3, 4):
                    roe = roe_raw * 4.0              # Q1 → 年化
                elif month in (6, 7, 8):
                    roe = roe_raw * 2.0              # H1 → 年化
                elif month in (9, 10):
                    roe = roe_raw * (4.0 / 3.0)      # Q3 → 年化
                else:
                    roe = roe_raw                    # 未知，直接用

            # 简化评估
            if roe >= 25 and gm >= 60:
                return self._l3_cfg.excellent  # 1.2
            elif roe >= 15 and gm >= 30:
                return self._l3_cfg.good  # 1.0
            elif roe >= 8:
                return self._l3_cfg.medium  # 0.8
            else:
                # 不直接 reject，让后续质量检查决定
                return self._l3_cfg.medium
        except Exception:
            pass
        return self._l3_cfg.good


# ── 快捷函数 ──

def quick_score(ts_code: str, token: str | None = None) -> FinalScore:
    """快捷打分 — 一行代码跑完整管线。"""
    from src.data_fetcher.tushare_client import TushareClient
    from src.data_fetcher.orchestrator import DataPoolOrchestrator
    client = TushareClient(token=token)
    orch = DataPoolOrchestrator(client)
    orch.snapshot_stock(ts_code)
    bundle = orch.get_bundle(ts_code)
    if bundle is None:
        raise RuntimeError(f"快照失败: {ts_code}")
    scorer = TurtleScorer(bundle)
    return scorer.score(ts_code)
