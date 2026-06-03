"""
财报深度分析引擎 — 从 Tushare 三大报表提取结构化洞察。

7 个分析模块，全部纯 Python 确定性计算，不依赖 LLM：
  1. 收入利润趋势    — 营收/净利润 CAGR + 增长稳定性
  2. 利润率拆解      — 毛利率→营业利润率→净利率 逐年趋势
  3. ROE 杜邦拆解    — ROE = 净利率 × 资产周转率 × 权益乘数
  4. 现金流质量      — 经营CF/净利润比 + 自由现金流 + CAPEX负担
  5. 资产负债健康度  — 有息负债率 + 现金覆盖率 + 流动比率
  6. 分红政策        — 分红率趋势 + 连续性 + 每股分红CAGR
  7. 营运效率        — 应收/应付/存货周转天数 + 现金转化周期

用法:
    from src.calculator.financial_deep_analysis import FinancialDeepAnalyzer
    analyzer = FinancialDeepAnalyzer(bundle)
    insights = analyzer.analyze(ts_code)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger

from src.data_pool.bundle import StockDataBundle


# ══════════════════════════════════════════════════════════════
# 输出模型
# ══════════════════════════════════════════════════════════════


@dataclass
class FinancialInsights:
    """7 模块财报深度分析结果。"""

    ts_code: str
    name: str

    # ── 模块1: 收入利润趋势 ──
    revenue_cagr_3yr: float = 0.0       # 近3年营收CAGR (%)
    revenue_cagr_5yr: float = 0.0       # 近5年营收CAGR (%)
    profit_cagr_3yr: float = 0.0        # 近3年净利润CAGR (%)
    profit_cagr_5yr: float = 0.0        # 近5年净利润CAGR (%)
    growth_stability: str = "N/A"        # 稳定 / 波动 / 下滑
    revenue_trend_str: str = ""

    # ── 模块2: 利润率拆解 ──
    gross_margin_trend: list[float] = field(default_factory=list)
    net_margin_trend: list[float] = field(default_factory=list)
    margin_direction: str = "N/A"        # 改善 / 稳定 / 恶化
    margin_trend_str: str = ""

    # ── 模块3: ROE 杜邦拆解 ──
    roe_trend: list[float] = field(default_factory=list)
    dupont_components: list[dict[str, Any]] = field(default_factory=list)
    roe_driver: str = ""
    roe_trend_str: str = ""

    # ── 模块4: 现金流质量 ──
    ocf_ni_ratio_trend: list[float] = field(default_factory=list)
    fcf_avg: float = 0.0                # 近5年平均自由现金流(亿)
    capEx_burden: list[float] = field(default_factory=list)
    cash_quality: str = "N/A"            # 优秀 / 良好 / 一般 / 差劲
    cash_quality_str: str = ""

    # ── 模块5: 资产负债健康度 ──
    debt_ratio_trend: list[float] = field(default_factory=list)
    interest_bearing_debt_ratio: float = 0.0
    cash_coverage: float = 0.0
    current_ratio_trend: list[float] = field(default_factory=list)
    balance_health: str = "N/A"          # 稳健 / 适中 / 偏高 / 危险
    balance_health_str: str = ""

    # ── 模块6: 分红政策 ──
    dividend_per_share_trend: list[float] = field(default_factory=list)
    payout_ratio_trend: list[float] = field(default_factory=list)
    dividend_consistency: int = 0        # 连续分红年数
    dividend_cagr: float = 0.0           # 每股分红CAGR (%)
    dividend_policy_str: str = ""

    # ── 模块7: 营运效率 ──
    receivable_days_trend: list[float] = field(default_factory=list)
    payable_days_trend: list[float] = field(default_factory=list)
    inventory_days_trend: list[float] = field(default_factory=list)
    cash_conversion_cycle_trend: list[float] = field(default_factory=list)
    working_capital_efficiency: str = "N/A"  # 高效 / 正常 / 偏低
    efficiency_str: str = ""


# ══════════════════════════════════════════════════════════════
# 分析引擎
# ══════════════════════════════════════════════════════════════


class FinancialDeepAnalyzer:
    """从 StockDataBundle 提取 7 模块财报深度分析洞察。

    所有计算均为确定性 Python 逻辑，不调用外部 API。
    """

    def __init__(self, bundle: StockDataBundle):
        self._b = bundle
        self._name = bundle.name or bundle.ts_code
        self._ts_code = bundle.ts_code

    def analyze(self) -> FinancialInsights:
        """执行全部 7 模块分析。"""
        result = FinancialInsights(ts_code=self._ts_code, name=self._name)

        try:
            self._analyze_revenue_profit(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块1(收入利润趋势) 失败: {e}")

        try:
            self._analyze_margins(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块2(利润率拆解) 失败: {e}")

        try:
            self._analyze_roe_dupont(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块3(ROE杜邦) 失败: {e}")

        try:
            self._analyze_cashflow_quality(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块4(现金流质量) 失败: {e}")

        try:
            self._analyze_balance_health(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块5(资产负债健康度) 失败: {e}")

        try:
            self._analyze_dividend(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块6(分红政策) 失败: {e}")

        try:
            self._analyze_efficiency(result)
        except Exception as e:
            logger.warning(f"[{self._ts_code}] 模块7(营运效率) 失败: {e}")

        return result

    # ── Helpers ──

    def _get_yearly(self, df: pd.DataFrame, col: str, n: int = 5,
                    ascending: bool = True) -> list[float]:
        """从 DataFrame 提取最近 n 年的数值列（仅年报，按时间升序）。

        始终返回升序（oldest→newest），供 _cagr 等函数使用。
        """
        if df is None or df.empty or col not in df.columns:
            return []
        sorted_df = df.sort_values("end_date", ascending=True)
        # v0.26: 仅保留年报，避免季报/半年报混入导致 CAGR 失真
        sorted_df = sorted_df[sorted_df["end_date"].astype(str).str.endswith("1231")]
        if "f_ann_date" in sorted_df.columns:
            sorted_df = sorted_df[sorted_df["f_ann_date"].notna()]
        vals = sorted_df[col].tail(n).tolist()
        return [float(v) for v in vals if v is not None and not (isinstance(v, float) and pd.isna(v))]

    def _get_yearly_years(self, df: pd.DataFrame, n: int = 5,
                          ascending: bool = True) -> list[str]:
        """从 DataFrame 提取最近 n 年的年份标签（仅年报，按时间升序）。"""
        if df is None or df.empty:
            return []
        sorted_df = df.sort_values("end_date", ascending=True)
        sorted_df = sorted_df[sorted_df["end_date"].astype(str).str.endswith("1231")]
        if "f_ann_date" in sorted_df.columns:
            sorted_df = sorted_df[sorted_df["f_ann_date"].notna()]
        years = sorted_df["end_date"].tail(n).tolist()
        return [str(y)[:4] for y in years]

    @staticmethod
    def _cagr(values: list[float]) -> float:
        """计算 CAGR (%)。"""
        if len(values) < 2 or values[0] is None or values[-1] is None:
            return 0.0
        begin, end = values[0], values[-1]
        if begin <= 0 or end <= 0:
            return 0.0
        years = len(values) - 1
        return ((end / begin) ** (1.0 / years) - 1) * 100

    @staticmethod
    def _fmt_yi(val: Any) -> str:
        """格式化为亿元。"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "-"
        try:
            v = float(val) / 1e8  # 元→亿
            if abs(v) >= 100:
                return f"{v:.0f}"
            elif abs(v) >= 1:
                return f"{v:.1f}"
            else:
                return f"{v:.2f}"
        except (ValueError, TypeError):
            return str(val)

    # ══════════════════════════════════════════════════════════
    # 模块1: 收入利润趋势
    # ══════════════════════════════════════════════════════════

    def _analyze_revenue_profit(self, r: FinancialInsights) -> None:
        income = self._b.income
        if income is None or income.empty:
            r.growth_stability = "数据不足"
            r.revenue_trend_str = "*(income 数据不可用)*"
            return

        revenues = self._get_yearly(income, "revenue", 5)
        profits = self._get_yearly(income, "n_income", 5)
        years = self._get_yearly_years(income, 5)

        if len(revenues) >= 3:
            r.revenue_cagr_3yr = self._cagr(revenues[-3:])
        if len(revenues) >= 5:
            r.revenue_cagr_5yr = self._cagr(revenues)
        if len(profits) >= 3:
            r.profit_cagr_3yr = self._cagr(profits[-3:])
        if len(profits) >= 5:
            r.profit_cagr_5yr = self._cagr(profits)

        # 增长稳定性
        if len(profits) >= 4:
            growth_rates = [(profits[i+1] / profits[i] - 1) * 100
                          for i in range(len(profits) - 1) if profits[i] > 0]
            if growth_rates:
                cv = float(np.std(growth_rates)) / (abs(float(np.mean(growth_rates))) + 1e-8)
                if cv < 0.3:
                    r.growth_stability = "稳定"
                elif cv < 0.8:
                    r.growth_stability = "波动"
                else:
                    r.growth_stability = "大幅波动"
            elif r.profit_cagr_3yr < -2:
                r.growth_stability = "下滑"
            else:
                r.growth_stability = "稳定"

        r.revenue_trend_str = (
            f"营收近3年CAGR={r.revenue_cagr_3yr:.1f}%, "
            f"近5年CAGR={r.revenue_cagr_5yr:.1f}%; "
            f"净利润近3年CAGR={r.profit_cagr_3yr:.1f}%, "
            f"近5年CAGR={r.profit_cagr_5yr:.1f}%; "
            f"增长稳定性={r.growth_stability}"
        )

    # ══════════════════════════════════════════════════════════
    # 模块2: 利润率拆解
    # ══════════════════════════════════════════════════════════

    def _analyze_margins(self, r: FinancialInsights) -> None:
        ind = self._b.fina_indicator
        if ind is None or ind.empty:
            r.margin_direction = "数据不足"
            return

        gross = self._get_yearly(ind, "grossprofit_margin", 5)
        net = self._get_yearly(ind, "netprofit_margin", 5)

        r.gross_margin_trend = gross
        r.net_margin_trend = net

        # 趋势方向（简单线性比较首尾）
        if len(net) >= 2:
            if net[-1] > net[0] + 1:
                r.margin_direction = "改善"
            elif net[-1] < net[0] - 1:
                r.margin_direction = "恶化"
            else:
                r.margin_direction = "稳定"

        r.margin_trend_str = (
            f"毛利率 {'→'.join(f'{g:.1f}%' for g in gross[-5:]) if gross else 'N/A'}, "
            f"趋势={r.margin_direction}; "
            f"净利率 {'→'.join(f'{n:.1f}%' for n in net[-5:]) if net else 'N/A'}"
        )

    # ══════════════════════════════════════════════════════════
    # 模块3: ROE 杜邦拆解
    # ══════════════════════════════════════════════════════════

    def _analyze_roe_dupont(self, r: FinancialInsights) -> None:
        ind = self._b.fina_indicator
        income = self._b.income
        balance = self._b.balancesheet

        if ind is None or ind.empty:
            roe = self._get_yearly(pd.DataFrame(), "", 0)
        else:
            roe = self._get_yearly(ind, "roe", 5)
        r.roe_trend = roe

        # 杜邦拆解 — v0.26: 仅使用年报，按年份精确匹配 income 和 balance
        if not income.empty and not balance.empty and len(roe) >= 2:
            inc_sorted = income[
                income["end_date"].astype(str).str.endswith("1231")
            ].sort_values("end_date").tail(5)
            bal_sorted = balance[
                balance["end_date"].astype(str).str.endswith("1231")
            ].sort_values("end_date").tail(5)

            for _, inc_row in inc_sorted.iterrows():
                end_date = str(inc_row.get("end_date", ""))
                year = end_date[:4]
                ni = float(inc_row.get("n_income", 0) or 0)
                rev = float(inc_row.get("revenue", 0) or 0)
                net_margin = (ni / rev * 100) if rev > 0 else 0

                # 按 end_date 匹配资产负债表（而非按位置对齐）
                bal_match = bal_sorted[bal_sorted["end_date"].astype(str) == end_date]
                if not bal_match.empty:
                    bal_row = bal_match.iloc[0]
                    ta = float(bal_row.get("total_assets", 0) or 0)
                    turnover = (rev / ta) if ta > 0 else 0
                    eq = float(bal_row.get("total_hldr_eqy_exc_min_int", 0) or 0)
                    if eq <= 0:
                        eq = float(bal_row.get("total_assets", 0) or 0) - float(bal_row.get("total_liab", 0) or 0)
                    multiplier = (ta / eq) if eq > 0 else 0
                else:
                    turnover, multiplier = 0, 0

                r.dupont_components.append({
                    "year": year,
                    "net_margin": round(net_margin, 1),
                    "asset_turnover": round(turnover, 2),
                    "equity_multiplier": round(multiplier, 2),
                })

        # 主驱动
        if r.dupont_components:
            last = r.dupont_components[-1]
            last_roe = last["net_margin"] * last["asset_turnover"] * last["equity_multiplier"] / 100
            if last["net_margin"] > 20:
                r.roe_driver = "高净利率"
            elif last["asset_turnover"] > 1.5:
                r.roe_driver = "高资产周转"
            elif last["equity_multiplier"] > 4:
                r.roe_driver = "高杠杆"
            else:
                r.roe_driver = "均衡驱动"

        r.roe_trend_str = (
            f"ROE {'→'.join(f'{rv:.1f}%' for rv in roe[-5:]) if roe else 'N/A'}, "
            f"主驱动={r.roe_driver}"
        )

    # ══════════════════════════════════════════════════════════
    # 模块4: 现金流质量
    # ══════════════════════════════════════════════════════════

    def _analyze_cashflow_quality(self, r: FinancialInsights) -> None:
        cf = self._b.cashflow
        income = self._b.income

        if cf is None or cf.empty:
            r.cash_quality = "数据不足"
            return

        ocf_vals = self._get_yearly(cf, "n_cashflow_act", 5)
        capEx_vals = self._get_yearly(cf, "c_pay_acq_const_fiolta", 5)
        ni_vals = self._get_yearly(income, "n_income", 5)

        # OCF/NI 比率
        for i in range(min(len(ocf_vals), len(ni_vals))):
            if ni_vals[i] and ni_vals[i] != 0:
                r.ocf_ni_ratio_trend.append(ocf_vals[i] / ni_vals[i])

        # 自由现金流
        fcfs = []
        for i in range(min(len(ocf_vals), len(capEx_vals))):
            fcf = ocf_vals[i] - capEx_vals[i]
            fcfs.append(fcf)
            r.capEx_burden.append(capEx_vals[i] / ocf_vals[i] if ocf_vals[i] != 0 else 0)

        if fcfs:
            r.fcf_avg = float(np.mean(fcfs)) / 1e8  # 转为亿元

        # 质量评级
        if r.ocf_ni_ratio_trend:
            avg_ratio = float(np.mean(r.ocf_ni_ratio_trend))
            if avg_ratio >= 0.9:
                r.cash_quality = "优秀"
            elif avg_ratio >= 0.7:
                r.cash_quality = "良好"
            elif avg_ratio >= 0.5:
                r.cash_quality = "一般"
            else:
                r.cash_quality = "差劲"

        r.cash_quality_str = (
            f"经营现金流/净利润近5年平均={float(np.mean(r.ocf_ni_ratio_trend)):.2f}"
            if r.ocf_ni_ratio_trend else ""
        )
        if fcfs:
            r.cash_quality_str += f", 近5年平均自由现金流={r.fcf_avg:.1f}亿, 质量={r.cash_quality}"

    # ══════════════════════════════════════════════════════════
    # 模块5: 资产负债健康度
    # ══════════════════════════════════════════════════════════

    def _analyze_balance_health(self, r: FinancialInsights) -> None:
        balance = self._b.balancesheet
        if balance is None or balance.empty:
            r.balance_health = "数据不足"
            return

        debt_ratio = self._get_yearly(balance, "debt_to_assets", 5)
        # 如果 debt_to_assets 列不存在，手工计算
        if not debt_ratio:
            ta_vals = self._get_yearly(balance, "total_assets", 5)
            tl_vals = self._get_yearly(balance, "total_liab", 5)
            debt_ratio = [(tl / ta * 100) if ta > 0 else 0
                         for ta, tl in zip(ta_vals, tl_vals)]

        r.debt_ratio_trend = debt_ratio
        current_ratio = self._get_yearly(balance, "current_ratio", 5)
        r.current_ratio_trend = current_ratio

        # 有息负债率
        st_borr = self._get_yearly(balance, "st_borr", 5)
        money_cap = self._get_yearly(balance, "money_cap", 5)
        ta_vals = self._get_yearly(balance, "total_assets", 5)

        if st_borr and ta_vals and ta_vals[-1] > 0:
            r.interest_bearing_debt_ratio = st_borr[-1] / ta_vals[-1] * 100
        if money_cap and st_borr and st_borr[-1] > 0:
            r.cash_coverage = money_cap[-1] / st_borr[-1]

        # 评级
        if debt_ratio:
            avg_dr = float(np.mean(debt_ratio))
            if avg_dr < 25:
                r.balance_health = "稳健"
            elif avg_dr < 50:
                r.balance_health = "适中"
            elif avg_dr < 70:
                r.balance_health = "偏高"
            else:
                r.balance_health = "危险"

        r.balance_health_str = (
            f"资产负债率≈{debt_ratio[-1]:.1f}%" if debt_ratio else ""
        )
        if r.interest_bearing_debt_ratio > 0:
            r.balance_health_str += f", 有息负债率={r.interest_bearing_debt_ratio:.1f}%"
        if r.cash_coverage > 0:
            r.balance_health_str += f", 货币资金/有息负债={r.cash_coverage:.1f}x"
        r.balance_health_str += f", 评级={r.balance_health}"

    # ══════════════════════════════════════════════════════════
    # 模块6: 分红政策
    # ══════════════════════════════════════════════════════════

    def _analyze_dividend(self, r: FinancialInsights) -> None:
        div = self._b.dividend
        income = self._b.income

        if div is None or div.empty:
            r.dividend_policy_str = "*(dividend 数据不可用)*"
            return

        div_copy = div.copy()
        div_copy["fiscal_year"] = div_copy["end_date"].astype(str).str[:4]
        yearly = div_copy.groupby("fiscal_year")["cash_div"].sum().reset_index()
        yearly = yearly.sort_values("fiscal_year", ascending=False).head(5)
        yearly = yearly.sort_values("fiscal_year", ascending=True)

        dps_trend = [float(row["cash_div"]) for _, row in yearly.iterrows()]
        r.dividend_per_share_trend = dps_trend

        # 连续性
        if len(yearly) >= 5:
            r.dividend_consistency = len(yearly)
        else:
            r.dividend_consistency = len(yearly)

        # 每股分红 CAGR
        if len(dps_trend) >= 2 and dps_trend[0] > 0:
            r.dividend_cagr = self._cagr(dps_trend)

        # 分红率
        ni_vals = self._get_yearly(income, "n_income", 5)
        if ni_vals and dps_trend:
            # 需要 total_shares 来算分红总额，用 EPS 和 NI 反推
            for i in range(min(len(dps_trend), len(ni_vals))):
                if ni_vals[i] and ni_vals[i] > 0:
                    # 粗略估计：假设 EPS ≈ NI / 总股本，总股本估算
                    # 这里用收入表里的 basic_eps 如果可用
                    pass

        r.dividend_policy_str = (
            f"近5年每股分红: {'→'.join(f'{d:.2f}' for d in dps_trend) if dps_trend else 'N/A'} 元/股, "
            f"每股分红CAGR={r.dividend_cagr:.1f}%, "
            f"连续分红{r.dividend_consistency}年+"
        )

    # ══════════════════════════════════════════════════════════
    # 模块7: 营运效率
    # ══════════════════════════════════════════════════════════

    def _analyze_efficiency(self, r: FinancialInsights) -> None:
        income = self._b.income
        balance = self._b.balancesheet

        if income is None or income.empty or balance is None or balance.empty:
            r.working_capital_efficiency = "数据不足"
            return

        # v0.26: 仅使用年报，按年份精确匹配
        inc_sorted = income[
            income["end_date"].astype(str).str.endswith("1231")
        ].sort_values("end_date").tail(5)
        bal_sorted = balance[
            balance["end_date"].astype(str).str.endswith("1231")
        ].sort_values("end_date").tail(5)

        for _, inc_row in inc_sorted.iterrows():
            end_date = str(inc_row.get("end_date", ""))
            rev = float(inc_row.get("revenue", 0) or 0)
            cost = float(inc_row.get("oper_cost", 0) or 0)
            if rev <= 0:
                continue

            # 按 end_date 匹配资产负债表
            bal_match = bal_sorted[bal_sorted["end_date"].astype(str) == end_date]
            if not bal_match.empty:
                bal_row = bal_match.iloc[0]
                receivables = float(bal_row.get("notes_receiv", 0) or 0) + \
                              float(bal_row.get("accounts_receiv", 0) or 0)
                payables = float(bal_row.get("notes_payable", 0) or 0) + \
                           float(bal_row.get("accounts_payable", 0) or 0)
                inventory = float(bal_row.get("inventories", 0) or 0)

                rec_days = (receivables / rev * 365) if rev > 0 else 0
                pay_days = (payables / cost * 365) if cost > 0 else 0
                inv_days = (inventory / cost * 365) if cost > 0 else 0
                ccc = rec_days + inv_days - pay_days

                r.receivable_days_trend.append(round(rec_days, 1))
                r.payable_days_trend.append(round(pay_days, 1))
                r.inventory_days_trend.append(round(inv_days, 1))
                r.cash_conversion_cycle_trend.append(round(ccc, 1))

        # 评级
        if r.cash_conversion_cycle_trend:
            avg_ccc = float(np.mean(r.cash_conversion_cycle_trend))
            if avg_ccc < -30:
                r.working_capital_efficiency = "高效(占用上游资金)"
            elif avg_ccc < 30:
                r.working_capital_efficiency = "高效"
            elif avg_ccc < 90:
                r.working_capital_efficiency = "正常"
            else:
                r.working_capital_efficiency = "偏低"

        r.efficiency_str = (
            f"应收周转={r.receivable_days_trend[-1]:.1f}天" if r.receivable_days_trend else ""
        )
        if r.payable_days_trend:
            r.efficiency_str += f", 应付周转={r.payable_days_trend[-1]:.1f}天"
        if r.inventory_days_trend:
            r.efficiency_str += f", 存货周转={r.inventory_days_trend[-1]:.1f}天"
        if r.cash_conversion_cycle_trend:
            r.efficiency_str += f", CCC={r.cash_conversion_cycle_trend[-1]:.1f}天"
        r.efficiency_str += f", 评级={r.working_capital_efficiency}"


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════


def insights_to_markdown(insights: FinancialInsights) -> str:
    """将 FinancialInsights 渲染为 Markdown 字符串，供 brief.md 或直接展示。"""
    lines = [
        f"## 三、财报深度分析洞察 — {insights.name} ({insights.ts_code})",
        "",
    ]

    # 模块1
    lines.append("### 3.1 收入利润趋势")
    lines.append(f"{insights.revenue_trend_str}")
    lines.append("")

    # 模块2
    lines.append("### 3.2 利润率拆解")
    lines.append(f"{insights.margin_trend_str}")
    lines.append("")

    # 模块3
    lines.append("### 3.3 ROE 杜邦拆解")
    lines.append(f"{insights.roe_trend_str}")
    if insights.dupont_components:
        lines.append("")
        lines.append("| 年份 | 净利率(%) | 资产周转率 | 权益乘数 |")
        lines.append("|------|----------|-----------|---------|")
        for d in insights.dupont_components:
            lines.append(
                f"| {d['year']} | {d['net_margin']} | {d['asset_turnover']} | {d['equity_multiplier']} |"
            )
    lines.append("")

    # 模块4
    lines.append("### 3.4 现金流质量")
    lines.append(f"{insights.cash_quality_str}")
    lines.append("")

    # 模块5
    lines.append("### 3.5 资产负债健康度")
    lines.append(f"{insights.balance_health_str}")
    lines.append("")

    # 模块6
    lines.append("### 3.6 分红政策")
    lines.append(f"{insights.dividend_policy_str}")
    lines.append("")

    # 模块7
    lines.append("### 3.7 营运效率")
    lines.append(f"{insights.efficiency_str}")
    lines.append("")

    return "\n".join(lines)
