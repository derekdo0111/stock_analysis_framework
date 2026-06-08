"""
OE 单路径计算 + 维持性CAPEX系数 + 四级质量验证。

路径B: OE_cf = 经营CF净额 - 总CAPEX × 维持性CAPEX系数 → 供OE质量验证
v0.19: 删除路径A（数据不可靠），质量验证从5级→4级。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from src.core.data.pool.bundle import StockDataBundle
from src.turtle.rules.loader import load_rules


@dataclass
class OECalculationResult:
    """OE 计算结果 — v0.19: 只保留路径B，删路径A。"""

    ts_code: str
    maintenance_coefficient: float = 0.60

    # 路径B — 现金流路径
    oe_cf_values: list[float] = field(default_factory=list)
    oe_cf_median: float = 0.0
    oe_cf_mean: float = 0.0
    oe_cf_std: float = 0.0
    oe_cf_cv: float = 0.0  # 变异系数
    oe_cf_cagr_3y: float = 0.0

    # 行业先验
    industry_prior: float = 0.60

    # 资产轻重三因子
    capex_to_revenue_pct: float = 0.0
    fixed_asset_turnover: float = 0.0
    depreciation_to_revenue_pct: float = 0.0
    asset_intensity_score: float = 0.0

    # 质量验证
    oe_to_profit_ratio: float = 0.0
    bs_unexplained_diff_pct: float = 0.0

    # 标签
    quality_label: Literal["🟢 可信", "🟡 存疑", "🔴 不可靠"] = "🟢 可信"
    quality_penalty_total: int = 0


class OECalculator:
    """OE 计算器 — v0.19 单路径。

    步骤:
    1. 确定维持性CAPEX系数（行业先验×0.4 + 资产轻重×0.6）
    2. 计算路径B OE_cf（5年）
    3. 四级质量验证（删除利润→现金转化率）
    4. 输出 OE 质量标签
    所有数据从 StockDataBundle 读取。
    """

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._rules = load_rules()
        self._tc = self._rules.turtle_constants
        self._oe_cfg = self._tc.owners_earnings

    def calculate(self, ts_code: str, industry: str = "") -> OECalculationResult:
        result = OECalculationResult(ts_code=ts_code)

        # Step 1: 确定维持性CAPEX系数
        result.maintenance_coefficient = self._determine_maintenance_coefficient(ts_code, industry, result)

        # Step 2: 路径B — OE_cf (5年)
        self._calc_oe_path_b(ts_code, result)

        # Step 3: 四级质量验证
        self._run_quality_checks(result)

        # Step 4: 质量标签
        self._assign_quality_label(result)

        return result

    def _determine_maintenance_coefficient(
        self, ts_code: str, industry: str, result: OECalculationResult
    ) -> float:
        cfg = self._oe_cfg.maintenance_capex_coefficient
        ip = cfg.industry_priors

        # 行业先验 (权重40%)
        industry_map = {
            "白酒": ip.consumer_staples,
            "食品": ip.consumer_staples,
            "饮料": ip.consumer_staples,
            "医药": ip.healthcare,
            "医疗": ip.healthcare,
            "家电": ip.consumer_discretionary,
            "汽车": ip.consumer_discretionary,
            "公用事业": ip.utility,
            "电力": ip.utility,
            "钢铁": ip.materials,
            "有色": ip.materials,
            "化工": ip.materials,
            "科技": ip.technology,
        }
        prior = ip.default
        for kw, v in industry_map.items():
            if kw in industry:
                prior = v
                break
        result.industry_prior = prior

        # 资产轻重评估 (权重60%) — 三因子平均
        indicators = cfg.asset_intensity_indicators
        try:
            # 拉取5年数据计算三因子
            revenue_5y = self._get_5y_revenue(ts_code)
            if revenue_5y and any(revenue_5y):
                rev_avg = float(np.mean([r for r in revenue_5y if r != 0]))
                # 因子1: CAPEX/营收
                capex_5y = self._get_5y_capex(ts_code)
                if capex_5y and any(capex_5y):
                    capex_avg = float(np.mean([c for c in capex_5y if c != 0]))
                    if rev_avg > 0:
                        result.capex_to_revenue_pct = (capex_avg / rev_avg) * 100

                # 因子2: 固定资产周转率
                fa_5y = self._get_5y_fixed_assets(ts_code)
                if fa_5y and any(fa_5y):
                    fa_avg = float(np.mean([f for f in fa_5y if f != 0]))
                    if fa_avg > 0:
                        result.fixed_asset_turnover = rev_avg / fa_avg

                # 因子3: 折旧/营收 (用CAPEX的55%粗略估计折旧)
                if result.capex_to_revenue_pct > 0:
                    result.depreciation_to_revenue_pct = result.capex_to_revenue_pct * 0.55

            # 三因子打分
            scores = []
            # CAPEX/营收
            cr = result.capex_to_revenue_pct
            if cr > 0:
                s = self._score_asset_indicator(cr, indicators["capex_to_revenue"]["scoring"])
                scores.append(s)
            # 固定资产周转率
            ft = result.fixed_asset_turnover
            if ft > 0:
                s = self._score_asset_indicator(ft, indicators["fixed_asset_turnover"]["scoring"])
                scores.append(s)
            # 折旧/营收
            dr = result.depreciation_to_revenue_pct
            if dr > 0:
                s = self._score_asset_indicator(dr, indicators["depreciation_to_revenue"]["scoring"])
                scores.append(s)

            if scores:
                result.asset_intensity_score = float(np.mean(scores))
            else:
                result.asset_intensity_score = prior  # fallback to industry prior
        except Exception:
            result.asset_intensity_score = prior

        # 最终系数 = 行业先验×0.4 + 资产轻重得分×0.6
        coefficient = prior * cfg.prior_weight + result.asset_intensity_score * cfg.asset_intensity_weight
        return round(coefficient, 4)

    def _calc_oe_path_b(self, ts_code: str, result: OECalculationResult) -> None:
        """路径B: OE_cf = 经营CF净额 - 总CAPEX × 维持性CAPEX系数"""
        try:
            df = self._bundle.cashflow
            if len(df) < 2:
                return
            # 只取年末数据（end_date=YYYY1231），过滤季报
            df = df[df["end_date"].astype(str).str.endswith("1231")]
            df = df.sort_values("end_date", ascending=False).head(5)
            values = []
            for _, row in df.iterrows():
                op_cf = row.get("n_cashflow_act") or 0
                capex = row.get("c_pay_acq_const_fiolta") or 0
                oe = op_cf - capex * result.maintenance_coefficient
                values.append(oe)
            result.oe_cf_values = values

            if values:
                result.oe_cf_median = float(np.median(values))
                result.oe_cf_mean = float(np.mean(values))
                result.oe_cf_std = float(np.std(values))
                if result.oe_cf_mean != 0:
                    result.oe_cf_cv = abs(result.oe_cf_std / result.oe_cf_mean)
                # 近3年CAGR — 仅当首尾同号时计算，否则留0（质量验证会扣分）
                # v0.19 fix: 3个数据点→2个增长期间，应**(1/2)
                if len(values) >= 3:
                    recent = values[:3]
                    first, last = recent[0], recent[-1]
                    if last and last != 0 and first * last > 0:
                        result.oe_cf_cagr_3y = (first / last) ** (1 / 2) - 1
        except Exception:
            pass

    def _run_quality_checks(self, result: OECalculationResult) -> None:
        """四级质量验证 (v0.19: 删除利润→现金转化率)。"""
        qc = self._oe_cfg.quality_checks
        total_penalty = 0

        # 1. OE_cf/净利润
        try:
            df = self._bundle.income
            df = df.sort_values("end_date", ascending=False).head(5)
            profits = [float(r.get("n_income") or 0) for _, r in df.iterrows()]
            if profits and result.oe_cf_values:
                med_profit = float(np.median([p for p in profits if p != 0]))
                if med_profit > 0:
                    ratio = result.oe_cf_median / med_profit
                    result.oe_to_profit_ratio = ratio
                    for t in qc.oe_to_profit_ratio.thresholds:
                        min_v, max_v = t.min, t.max
                        penalty = t.score or 0
                        if (min_v is None or ratio >= min_v) and (max_v is None or ratio < max_v):
                            total_penalty += penalty
                            break
        except Exception:
            pass

        # 2. OE稳定性 (CV)
        for t in qc.oe_stability.thresholds:
            min_v, max_v = t.min, t.max
            penalty = t.score or 0
            if (min_v is None or result.oe_cf_cv >= min_v) and (max_v is None or result.oe_cf_cv <= max_v):
                total_penalty += penalty
                break

        # 3. OE趋势 (3yr CAGR)
        for t in qc.oe_trend.thresholds:
            min_v = t.min
            penalty = t.score or 0
            if min_v is not None and result.oe_cf_cagr_3y >= min_v:
                break
            if min_v is None or result.oe_cf_cagr_3y < (min_v or 0):
                total_penalty += penalty
                break

        # 4. 资产负债表现金一致性 (BS Consistency)
        try:
            df_bs = self._bundle.balancesheet.sort_values("end_date", ascending=False)
            if len(df_bs) >= 5:
                bs_now = df_bs.iloc[0]
                bs_5y_ago = df_bs.iloc[-1]
                cash_now = bs_now.get("money_cap") or 0
                debt_now = (bs_now.get("st_borrow") or 0) + (bs_now.get("lt_borrow") or 0) + (bs_now.get("bonds_payable") or 0)
                cash_5y = bs_5y_ago.get("money_cap") or 0
                debt_5y = (bs_5y_ago.get("st_borrow") or 0) + (bs_5y_ago.get("lt_borrow") or 0) + (bs_5y_ago.get("bonds_payable") or 0)
                net_cash_change = (cash_now - debt_now) - (cash_5y - debt_5y)
                cum_oe = sum(result.oe_cf_values)
                if cum_oe and cum_oe != 0:
                    div_paid = 0  # 粗略估计
                    unexplained = cum_oe - net_cash_change - div_paid
                    result.bs_unexplained_diff_pct = abs(unexplained / cum_oe) * 100
                    if result.bs_unexplained_diff_pct > qc.bs_consistency.threshold_pct:
                        total_penalty += qc.bs_consistency.penalty or 3
        except Exception:
            pass

        result.quality_penalty_total = int(total_penalty)

    def _assign_quality_label(self, result: OECalculationResult) -> None:
        """分配 OE 质量标签（三级前置）。"""
        ql = self._oe_cfg.quality_label
        profit_ratio_ok = result.oe_to_profit_ratio >= 0.8
        cv_ok = result.oe_cf_cv <= 0.3

        if profit_ratio_ok and cv_ok:
            result.quality_label = "🟢 可信"
        elif (result.oe_to_profit_ratio < 0.5) or (result.oe_cf_cv > 0.5):
            result.quality_label = "🔴 不可靠"
        else:
            result.quality_label = "🟡 存疑"

    # ── 数据拉取辅助方法 ──────────────────────────────────────

    def _get_5y_revenue(self, ts_code: str) -> list[float]:
        try:
            df = self._bundle.income
            df = df[df["end_date"].astype(str).str.endswith("1231")]
            df = df.sort_values("end_date", ascending=False).head(5)
            return [float(r.get("total_revenue") or 0) for _, r in df.iterrows()]
        except Exception:
            return []

    def _get_5y_capex(self, ts_code: str) -> list[float]:
        try:
            df = self._bundle.cashflow
            df = df[df["end_date"].astype(str).str.endswith("1231")]
            df = df.sort_values("end_date", ascending=False).head(5)
            return [float(r.get("c_pay_acq_const_fiolta") or 0) for _, r in df.iterrows()]
        except Exception:
            return []

    def _get_5y_fixed_assets(self, ts_code: str) -> list[float]:
        try:
            df = self._bundle.balancesheet
            df = df[df["end_date"].astype(str).str.endswith("1231")]
            df = df.sort_values("end_date", ascending=False).head(5)
            return [float(r.get("fix_assets") or 0) for _, r in df.iterrows()]
        except Exception:
            return []

    @staticmethod
    def _score_asset_indicator(value: float, scoring: dict) -> float:
        """三因子打分: light/medium/heavy → score."""
        for level, cfg in scoring.items():
            min_v = cfg.get("min")
            max_v = cfg.get("max")
            score = cfg.get("score", 0.5)
            if min_v is not None and max_v is not None:
                if min_v <= value < max_v:
                    return score
            elif min_v is not None:
                if value >= min_v:
                    return score
            elif max_v is not None:
                if value <= max_v:
                    return score
        return 0.55  # 默认中资产
