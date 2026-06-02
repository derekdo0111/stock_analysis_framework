"""
穿透回报率 (Penetration Return) 计算器 — v0.22。

PR = (当前可支配现金 × 分配比率 + 回购注销金额) / 最新收盘总市值

v0.22: 去除安全边际系数和红利税折扣，PR 直接反映数学真实回报。
       分配比率二档改为 mean(分红/净利润) 算术平均。
v0.21: 分配比率外推加回分红后计算，避免 money_cap 被分红抽干导致 ratio 虚高。

流程:
1. 计算当前可支配现金（DisposableCashCalculator）
2. 确定分配比率（一档：公告承诺 / 二档：历史分红/净利润算术平均）
3. 获取回购注销金额（Web+LLM提取）
4. 获取最新总市值
5. PR 计算
6. OE 质量验证 + 标签影响
7. L4 = max(0, min(40, 起点分 - 质量扣分))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from src.calculator.turtle_strategy.oe_calculator import OECalculationResult, OECalculator
from src.data_pool.bundle import StockDataBundle
from src.data_pool.schema.disposable_cash import DisposableCashCalculator, DisposableCashResult
from src.rules.loader import load_rules


@dataclass
class PRCalculationResult:
    """穿透回报率计算结果 — v0.22。"""

    ts_code: str
    pr_pct: float = 0.0  # PR (%)

    # v0.19 公式展开
    disposable_cash: float = 0.0  # 当前可支配现金(万元)
    distribution_ratio: float = 0.0  # 分配比率(%)
    distribution_source: str = ""  # "tier1_commitment" | "tier2_extrapolation"
    buyback_cancellation: float = 0.0  # 回购注销金额(万元)
    current_market_cap: float = 0.0  # 最新总市值(万元)

    # OE 数据（保留用于质量验证）
    oe_cf_median: float = 0.0
    oe_cf_mean: float = 0.0
    oe_cv: float = 0.0
    oe_cagr: float = 0.0
    oe_path_b_values: list[float] = field(default_factory=list)
    capex_coefficient: float = 0.0
    oe_quality_label: str = "🟢 可信"

    # L4 打分
    starting_score: float = 0.0
    quality_penalty: float = 0.0
    l4_score: float = 0.0
    l4_max: float = 40.0

    is_valid: bool = True
    invalid_reason: str = ""


class PRCalculator:
    """穿透回报率计算器 — v0.22。

    PR = (当前可支配现金 × 分配比率 + 回购注销金额) / 最新总市值
    所有数据从 StockDataBundle 读取。

    v0.22: 去除安全边际系数(×0.7/0.8)和红利税折扣(×0.9)，
           PR 直接反映数学真实回报。分配比率二档改为 mean(分红/净利润)。
    v0.21: 分配比率外推加回分红后计算，避免 money_cap 被分红抽干导致 ratio 虚高。
    """

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._oe_calc = OECalculator(bundle)
        self._dc_calc = DisposableCashCalculator(bundle)
        self._rules = load_rules()
        self._pr_cfg = self._rules.turtle_constants.penetration_return
        self._tax_cfg = self._rules.turtle_constants.tax

    def calculate(
        self, ts_code: str, industry: str = ""
    ) -> PRCalculationResult:
        result = PRCalculationResult(ts_code=ts_code)

        # ── Step 1: 可支配现金计算 ──
        dc_result = self._dc_calc.calculate(ts_code, restricted_cash=0.0)
        result.disposable_cash = dc_result.current

        # ── Step 2: 确定分配比率 ──
        ratio, ratio_source = self._determine_distribution_ratio(ts_code, dc_result)
        result.distribution_ratio = ratio
        result.distribution_source = ratio_source

        # ── Step 3: 回购注销金额 ──
        result.buyback_cancellation = self._get_buyback_cancellation()

        # ── Step 4: 最新总市值 ──
        result.current_market_cap = self._get_latest_market_cap(ts_code)

        # ── Step 5: PR 计算（v0.22: 无税率折扣，真实数学回报）──
        # 注：持股<1月需缴10%红利税，不在PR中预先扣除，报告备注
        distributable = result.disposable_cash * (result.distribution_ratio / 100)

        if result.current_market_cap > 0:
            result.pr_pct = round(
                (distributable + result.buyback_cancellation) / result.current_market_cap * 100, 2
            )

        # ── Step 6: OE 质量验证 ──
        oe_result = self._oe_calc.calculate(ts_code, industry)
        result.oe_cf_median = oe_result.oe_cf_median
        result.oe_cf_mean = oe_result.oe_cf_mean
        result.oe_cv = oe_result.oe_cf_cv
        result.oe_cagr = oe_result.oe_cf_cagr_3y
        result.oe_path_b_values = list(oe_result.oe_cf_values)
        result.capex_coefficient = oe_result.maintenance_coefficient
        result.oe_quality_label = oe_result.quality_label

        # ── Step 7: 起点分（三级阈值） ──
        result.starting_score = self._compute_starting_score(result.pr_pct)

        # ── Step 8: 质量扣分 ──
        result.quality_penalty = float(oe_result.quality_penalty_total)

        # ── Step 9: OE 质量标签影响 ──
        if oe_result.quality_label == "🔴 不可靠":
            result.l4_score = 0.0
            result.is_valid = False
            result.invalid_reason = "OE不可靠，L4=0，由Agent另行定性评估"
            return result

        if oe_result.quality_label == "🟡 存疑":
            result.quality_penalty += result.starting_score * 0.3

        result.l4_score = max(
            0.0, min(result.l4_max, result.starting_score - result.quality_penalty)
        )
        result.l4_score = round(result.l4_score, 2)

        return result

    # ── 分配比率 ─────────────────────────────────────────

    def _determine_distribution_ratio(
        self, ts_code: str, dc_result: DisposableCashResult
    ) -> tuple[float, str]:
        """确定分配比率（v0.22: 无安全边际折扣）。

        一档（优先）：公告分红承诺（原值，不打折）
        二档（降级）：历史 mean(分红/净利润) 算术平均

        Returns:
            (ratio, source)
        """
        # 一档：公告承诺（v0.22: 不再 × 0.8）
        commitment = getattr(self._bundle, "dividend_commitment", None)
        if commitment and commitment.has_commitment and commitment.ratio:
            return round(commitment.ratio, 2), "tier1_commitment"

        # 二档：历史外推
        ratio = self._extrapolate_from_history(ts_code, dc_result)
        return round(ratio, 2), "tier2_extrapolation"

    def _extrapolate_from_history(
        self, ts_code: str, dc_result: DisposableCashResult
    ) -> float:
        """二档外推（v0.22）: 历史 mean(年度分红总额 / 年度净利润) 算术平均。

        改用净利润做分母（独立于 DC，无循环依赖），算数平均（等权）。

        若数据不足，退回到 fallback（同逻辑但更保守）。
        """
        try:
            div_df = self._bundle.dividend
            income_df = self._bundle.income

            if div_df.empty or income_df.empty:
                return 30.0  # 行业默认值

            # 年度分红汇总（每股）—— 只取「实施」，避免同一分红在
            # 「股东大会通过」和「实施」两条记录中被重复计数
            annual_divs: dict[int, float] = {}
            if not div_df.empty and "end_date" in div_df.columns:
                for _, row in div_df.iterrows():
                    proc = str(row.get("div_proc", ""))
                    if proc != "实施":
                        continue
                    year = int(str(row.get("end_date", ""))[:4])
                    cash_per_share = float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))
                    annual_divs[year] = annual_divs.get(year, 0) + cash_per_share

            # 取近5年利润表年末数据（去重，Tushare 可能返回重复行）
            income_yearly = income_df[income_df["end_date"].astype(str).str.endswith("1231")].drop_duplicates(
                subset=["end_date"]
            ).sort_values("end_date", ascending=False).head(5)

            payout_ratios = []
            for _, row in income_yearly.iterrows():
                year = int(str(row.get("end_date", ""))[:4])
                np_val = float(row.get("n_income") or 0) / 1e4  # 元→万元
                if np_val <= 0 or year not in annual_divs:
                    continue
                total_share = self._get_year_end_total_share(ts_code, year)
                if total_share <= 0:
                    continue
                total_div = annual_divs[year] * total_share  # 万元
                payout_ratios.append(total_div / np_val * 100)

            if payout_ratios:
                return float(np.mean(payout_ratios))  # v0.22: 算术平均，无安全边际

        except Exception:
            pass

        return self._fallback_dividend_ratio()

    def _fallback_dividend_ratio(self) -> float:
        """退路（v0.22）: 历史 mean(分红/净利润) 算术平均。"""
        try:
            div_df = self._bundle.dividend
            income_df = self._bundle.income

            if div_df.empty or income_df.empty:
                return 30.0  # 行业默认值

            income_yearly = income_df[income_df["end_date"].astype(str).str.endswith("1231")].sort_values(
                "end_date", ascending=False
            ).head(5)

            annual_divs: dict[int, float] = {}
            total_shares: dict[int, float] = {}
            for _, row in div_df.iterrows():
                proc = str(row.get("div_proc", ""))
                if proc != "实施":
                    continue
                year = int(str(row.get("end_date", ""))[:4])
                annual_divs[year] = annual_divs.get(year, 0) + float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))

            payout_ratios = []
            for _, row in income_yearly.iterrows():
                year = int(str(row.get("end_date", ""))[:4])
                np_val = float(row.get("n_income") or 0) / 1e4  # 元→万元
                if np_val <= 0 or year not in annual_divs:
                    continue
                total_share = self._get_year_end_total_share(self._bundle.ts_code, year)
                if total_share <= 0:
                    continue
                total_div = annual_divs[year] * total_share
                payout_ratios.append(total_div / np_val * 100)

            if payout_ratios:
                return float(np.mean(payout_ratios))  # v0.22: 算术平均，无安全边际

        except Exception:
            pass

        return 30.0  # 行业默认值

    # ── 回购注销 ─────────────────────────────────────────

    def _get_buyback_cancellation(self) -> float:
        """获取回购注销金额。

        优先从 WebExtractor 提取的结果，降级到 Tushare 回购数据中
        标注「注销」的部分。
        """
        # 一档：Web+LLM 提取的回购注销金额
        buyback_info = getattr(self._bundle, "buyback_cancellation", None)
        if buyback_info and buyback_info.has_cancellation and buyback_info.amount > 0:
            return buyback_info.amount

        # 二档：Tushare 回购数据中筛选注销相关
        try:
            df = self._bundle.repurchase
            if df.empty:
                return 0.0

            # 筛选已完成/实施的回购
            proc_col = df["proc"].astype(str).str.strip()
            df = df[proc_col.isin(["实施", "完成", "已完成"])].copy()

            # 查找「注销」关键词（在 proc 字段或备注中）
            if "proc" in df.columns:
                cancel_mask = df["proc"].astype(str).str.contains("注销", na=False)
                if cancel_mask.any() and "amount" in df.columns:
                    return float(df.loc[cancel_mask, "amount"].sum())
        except Exception:
            pass

        return 0.0

    # ── 市值 ─────────────────────────────────────────────

    def _get_latest_market_cap(self, ts_code: str) -> float:
        """获取最新收盘总市值（万元）。"""
        try:
            df = self._bundle.daily_basic.sort_values("trade_date", ascending=False)
            if not df.empty:
                mv = df.iloc[0].get("total_mv")
                if mv and float(mv) > 0:
                    return float(mv)
        except Exception:
            pass
        return 0.0

    def _get_year_end_total_share(self, ts_code: str, year: int) -> float:
        """获取年末总股本（万股）。

        降级策略: 1231 → 前14天递减 → 该年任意交易日
        """
        try:
            end_date = f"{year}1231"
            df = self._bundle.daily_basic
            row = df[df["trade_date"].astype(str) == end_date]
            if not row.empty:
                ts = row.iloc[0].get("total_share")
                if ts and float(ts) > 0:
                    return float(ts)
        except Exception:
            pass

        # fallback: 往前找最近交易日
        for day_offset in range(1, 15):
            try:
                day = 31 - day_offset
                if day < 1:
                    break
                alt_date = f"{year}12{day:02d}"
                row = df[df["trade_date"].astype(str) == alt_date]
                if not row.empty:
                    ts = row.iloc[0].get("total_share")
                    if ts and float(ts) > 0:
                        return float(ts)
            except Exception:
                continue

        # fallback 2: 该年任意交易日
        try:
            df_year = df[df["trade_date"].astype(str).str.startswith(str(year))]
            df_year = df_year.sort_values("trade_date", ascending=False)
            if not df_year.empty:
                ts = df_year.iloc[0].get("total_share")
                if ts and float(ts) > 0:
                    return float(ts)
        except Exception:
            pass

        return 0.0

    # ── 阈值打分 ──────────────────────────────────────────

    def _compute_starting_score(self, pr_pct: float) -> float:
        """PR 三级阈值 → 起点分。"""
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
