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

from dataclasses import dataclass

from src.data_fetcher.tushare_client import TushareClient
from src.calculator.turtle_strategy.pr_calculator import PRCalculator
from src.calculator.turtle_strategy.l5_calculator import L5Calculator
from src.screener.l2_screener import L2Screener
from src.screener.classifier import CompanyClassifier
from src.rules.loader import load_rules


@dataclass
class FinalScore:
    """最终评分输出。"""
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

    # PR 详情
    pr_pct: float = 0.0
    oe_quality: str = ""

    # 商业模式
    business_model: str = "良"

    # 仓位
    position_pct: float = 0.0

    # 状态
    is_valid: bool = True
    skip_reason: str = ""


class TurtleScorer:
    """龟龟策略完整打分器 — 串联全部计算模块。"""

    def __init__(self, client: TushareClient):
        self._client = client
        self._l2 = L2Screener(client)
        self._classifier = CompanyClassifier(client)
        self._pr = PRCalculator(client)
        self._l5 = L5Calculator(client)
        self._rules = load_rules()
        self._scoring = self._rules.turtle_constants.scoring
        self._l3_cfg = self._rules.turtle_constants.business_model_multiplier

    def score(self, ts_code: str) -> FinalScore:
        """跑完整打分管线。"""
        result = FinalScore(ts_code=ts_code)

        # ── 获取基础信息 ──
        industry = ""
        try:
            df = self._client.stock_basic()
            row = df[df["ts_code"] == ts_code]
            if not row.empty:
                result.name = str(row.iloc[0].get("name", ""))
                industry = str(row.iloc[0].get("industry", ""))
        except Exception:
            pass

        # ── L2 ──
        l2 = self._l2.score(ts_code, result.name)
        if l2.eliminated:
            result.is_valid = False
            result.skip_reason = f"L2淘汰: {l2.eliminate_reason}"
            return result
        result.l2_score = l2.total

        # ── 公司分类 ──
        cls = self._classifier.classify(ts_code)
        if not cls.eligible:
            result.is_valid = False
            result.skip_reason = f"分类排除({cls.category}): {cls.reason}"
            return result

        # ── L3 商业模式乘数 ──
        # 简化: 根据基本面指标估算商业模式质量
        result.l3_multiplier = self._estimate_l3(ts_code, industry)

        if result.l3_multiplier == -1:  # "poor" → reject
            result.is_valid = False
            result.skip_reason = "商业模式判'差'，不进入最终评分"
            return result

        # ── L4 穿透回报率 ──
        pr = self._pr.calculate(ts_code, industry)
        result.l4_score = pr.l4_score
        result.pr_pct = pr.pr_pct
        result.oe_quality = pr.oe_quality_label
        if not pr.is_valid:
            result.l4_score = 0.0

        # ── L5 安全边际 ──
        l5 = self._l5.calculate(ts_code, industry)
        result.l5_score = l5.l5_score
        result.position_pct = l5.position_pct

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
        """
        try:
            fi = self._client.fina_indicator(ts_code=ts_code).head(1)
            if fi.empty:
                return self._l3_cfg.good

            roe = fi.iloc[0].get("roe") or 0
            gm = fi.iloc[0].get("grossprofit_margin") or 0

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
    client = TushareClient(token=token)
    scorer = TurtleScorer(client)
    return scorer.score(ts_code)
