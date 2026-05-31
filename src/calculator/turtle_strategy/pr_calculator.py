"""
穿透回报率 (Penetration Return) 计算器。

PR = OE_cf_median(5年) / 当前总市值

流程:
1. 三级阈值起点分 (12%/8%/5%)
2. 五级质量扣分
3. OE质量标签影响 (🟢正常 → 🟡×0.7 → 🔴L4=0)
4. L4 = max(0, min(40, 起点分 - 质量扣分))
"""

from __future__ import annotations

from dataclasses import dataclass

from src.calculator.turtle_strategy.oe_calculator import OECalculationResult, OECalculator
from src.data_fetcher.tushare_client import TushareClient
from src.rules.loader import load_rules


@dataclass
class PRCalculationResult:
    """穿透回报率计算结果。"""
    ts_code: str
    oe_cf_median: float = 0.0
    market_cap: float = 0.0  # 亿元
    pr_raw: float = 0.0
    pr_pct: float = 0.0

    # L4 打分
    starting_score: float = 0.0
    quality_penalty: float = 0.0
    l4_score: float = 0.0
    l4_max: float = 40.0

    # OE 质量
    oe_quality_label: str = "🟢 可信"
    is_valid: bool = True
    invalid_reason: str = ""


class PRCalculator:
    """穿透回报率计算器。"""

    def __init__(self, client: TushareClient):
        self._client = client
        self._oe_calc = OECalculator(client)
        self._rules = load_rules()
        self._pr_cfg = self._rules.turtle_constants.penetration_return
        self._ql_cfg = self._rules.turtle_constants.owners_earnings.quality_label

    def calculate(self, ts_code: str, industry: str = "") -> PRCalculationResult:
        result = PRCalculationResult(ts_code=ts_code)

        # Step 1: OE 计算
        oe_result = self._oe_calc.calculate(ts_code, industry)
        result.oe_cf_median = oe_result.oe_cf_median
        result.oe_quality_label = oe_result.quality_label

        # Step 2: 获取市值
        try:
            db = self._client.daily_basic(ts_code=ts_code)
            if not db.empty:
                total_mv = db.iloc[0].get("total_mv")  # 万元
                if total_mv:
                    result.market_cap = float(total_mv) / 10000  # 万元→亿元
        except Exception:
            pass

        # Step 3: 计算 PR
        if result.market_cap > 0:
            result.pr_raw = result.oe_cf_median / (result.market_cap * 1e8)
            result.pr_pct = result.pr_raw * 100

        # Step 4: 三级阈值起点分
        result.starting_score = self._compute_starting_score(result.pr_pct)

        # Step 5: 质量扣分
        result.quality_penalty = float(oe_result.quality_penalty_total)

        # Step 6: OE质量标签影响
        if oe_result.quality_label == "🔴 不可靠":
            result.l4_score = 0.0
            result.is_valid = False
            result.invalid_reason = "OE不可靠，L4=0，由Agent另行定性评估"
            return result

        if oe_result.quality_label == "🟡 存疑":
            result.quality_penalty += result.starting_score * 0.3  # 等效×0.7

        result.l4_score = max(0.0, min(result.l4_max, result.starting_score - result.quality_penalty))
        result.l4_score = round(result.l4_score, 2)

        return result

    def _compute_starting_score(self, pr_pct: float) -> float:
        """PR 三级阈值 → 起点分."""
        for t in self._pr_cfg.thresholds:
            min_v = t.min
            max_v = t.max
            if min_v is not None and max_v is not None:
                if min_v <= pr_pct < max_v:
                    return t.starting_score
            elif min_v is not None and max_v is None:
                if pr_pct >= min_v:
                    return t.starting_score
            elif min_v is None and max_v is not None:
                if pr_pct < max_v:
                    return t.starting_score
        return 0.0
