"""
L3 十二维商业模式评估计算器 — v0.23。

十二维度 (每维 0-2 分，满分 24 → 映射到 0-30 分)：
  盈利能力: ROE水平 / ROE稳定性 / ROIC-ROE差距 / 毛利率水平 / 毛利率稳定性
  成熟度:   CAPEX/经营CF / 总资产CAGR / 营收CAGR
  资本纪律: 分红持续性 / 股本变动
  治理:     管理层稳定性 / 盈利真实性

等级:
  20-24 → 优, 14-19 → 良, 8-13 → 中, 0-7 → 差
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.data_pool.bundle import StockDataBundle
from src.rules.loader import load_rules
from src.rules.schemas import BusinessModelConfig


@dataclass
class L3Result:
    """L3 商业模式评估结果。"""

    ts_code: str

    # 维度明细
    dim_scores: dict[str, dict] = field(default_factory=dict)  # dim_id → {score, label, group}
    total_dim_score: float = 0.0  # 0-24
    l3_score: float = 0.0  # 0-30 (scaled)

    # 等级
    level: str = ""  # 优/良/中/差
    level_description: str = ""

    # 分组汇总
    group_scores: dict[str, dict] = field(default_factory=dict)  # group → {score, max}


class L3Calculator:
    """L3 十二维商业模式评估器。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._rules = load_rules()
        self._cfg: BusinessModelConfig = self._rules.turtle_constants.business_model
        self._tax_rate = self._rules.turtle_constants.tax.corporate_income_tax

    def calculate(self, ts_code: str) -> L3Result:
        result = L3Result(ts_code=ts_code)

        dims = self._cfg.dimensions
        for dim in dims:
            dim_id = dim.id
            try:
                method = getattr(self, f"_eval_{dim_id}", None)
                if method:
                    score, label = method(dim)
                else:
                    score, label = 0, "未实现"
            except Exception:
                score, label = 0, "计算异常"

            result.dim_scores[dim_id] = {
                "score": score,
                "label": label or "",
                "name": dim.name,
                "group": dim.group,
            }
            result.total_dim_score += score

        result.total_dim_score = round(result.total_dim_score, 1)

        # 映射到 0-30 分
        if self._cfg.max_dim_score > 0:
            result.l3_score = round(
                min(self._cfg.max_score,
                    result.total_dim_score / self._cfg.max_dim_score * self._cfg.max_score), 2
            )
        else:
            result.l3_score = 0.0

        # 等级判定
        levels = self._cfg.levels
        if levels:
            ts = result.total_dim_score
            for lvl_name, lvl in sorted(levels.items(), key=lambda x: -(x[1].min or 0)):
                lvl_min = lvl.min
                lvl_max = lvl.max
                if lvl_min is not None and lvl_max is not None:
                    if lvl_min <= ts <= lvl_max:
                        result.level = lvl.label
                        result.level_description = lvl.description or ""
                        break
                elif lvl_min is not None:
                    if ts >= lvl_min:
                        result.level = lvl.label
                        result.level_description = lvl.description or ""
                        break
                elif lvl_max is not None:
                    if ts <= lvl_max:
                        result.level = lvl.label
                        result.level_description = lvl.description or ""
                        break

        # 分组汇总
        group_score_map: dict[str, float] = {}
        group_max_map: dict[str, float] = {}
        for dim_id, info in result.dim_scores.items():
            g = info["group"]
            group_score_map[g] = group_score_map.get(g, 0) + info["score"]
            group_max_map[g] = group_max_map.get(g, 0) + 2.0

        for g in group_score_map:
            result.group_scores[g] = {
                "score": group_score_map[g],
                "max": group_max_map[g],
            }

        return result

    # ═══════════════════════════════════════════════════
    # 盈利能力组 (5维)
    # ═══════════════════════════════════════════════════

    def _eval_roe_level(self, dim) -> tuple[float, str]:
        """ROE水平: 最新年报ROE(年化值)。"""
        try:
            roe = self._get_latest_annual_roe()
            return self._apply_thresholds(roe, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_roe_stability(self, dim) -> tuple[float, str]:
        """ROE稳定性: 近5年ROE变异系数。"""
        try:
            fi = self._bundle.fina_indicator.sort_values("end_date", ascending=False).head(25)
            annual = fi[fi["end_date"].astype(str).str.endswith("1231")].head(5)
            roes = [float(r.get("roe") or 0) for _, r in annual.iterrows()]
            roes = [r for r in roes if r != 0]
            if len(roes) >= 3:
                mean_val = np.mean(roes)
                if mean_val != 0:
                    cv = float(np.std(roes) / abs(mean_val))
                    return self._apply_thresholds(cv, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_roic_roe_gap(self, dim) -> tuple[float, str]:
        """ROIC-ROE差距: |ROIC - ROE|。"""
        try:
            roic = self._compute_roic()
            roe = self._get_latest_annual_roe()
            if roic is not None and roe != 0:
                gap = abs(roic - roe)
                return self._apply_thresholds(gap, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_gross_margin_level(self, dim) -> tuple[float, str]:
        """毛利率水平: 最新年报毛利率。"""
        try:
            fi = self._bundle.fina_indicator
            annual = fi[fi["end_date"].astype(str).str.endswith("1231")].head(1)
            if not annual.empty:
                gm = float(annual.iloc[0].get("grossprofit_margin") or 0)
                return self._apply_thresholds(gm, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_gross_margin_stability(self, dim) -> tuple[float, str]:
        """毛利率稳定性: 近5年毛利率变异系数。"""
        try:
            fi = self._bundle.fina_indicator.sort_values("end_date", ascending=False).head(25)
            annual = fi[fi["end_date"].astype(str).str.endswith("1231")].head(5)
            gms = [float(r.get("grossprofit_margin") or 0) for _, r in annual.iterrows()]
            gms = [g for g in gms if g != 0]
            if len(gms) >= 3:
                mean_val = np.mean(gms)
                if mean_val != 0:
                    cv = float(np.std(gms) / abs(mean_val))
                    return self._apply_thresholds(cv, dim)
        except Exception:
            pass
        return 0, "数据不足"

    # ═══════════════════════════════════════════════════
    # 成熟度组 (3维)
    # ═══════════════════════════════════════════════════

    def _eval_capex_to_operating_cf(self, dim) -> tuple[float, str]:
        """CAPEX/经营CF: 近5年均值百分比。"""
        try:
            cf = self._bundle.cashflow.sort_values("end_date", ascending=False).head(25)
            annual = cf[cf["end_date"].astype(str).str.endswith("1231")].head(5)
            ratios = []
            for _, row in annual.iterrows():
                op_cf = float(row.get("n_cashflow_act") or 0)
                capex = float(row.get("c_pay_acq_const_fiolta") or 0)
                if op_cf > 0:
                    ratios.append(capex / op_cf * 100)
            if ratios:
                mean_ratio = float(np.mean(ratios))
                return self._apply_thresholds(mean_ratio, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_total_assets_cagr(self, dim) -> tuple[float, str]:
        """总资产增速: 近5年总资产CAGR。"""
        try:
            bs = self._bundle.balancesheet.sort_values("end_date", ascending=False)
            annual = bs[bs["end_date"].astype(str).str.endswith("1231")].head(5)
            assets = [float(r.get("total_assets") or 0) for _, r in annual.iterrows()]
            assets = [a for a in assets if a > 0]
            if len(assets) >= 2 and assets[-1] > 0:
                cagr = ((assets[0] / assets[-1]) ** (1 / (len(assets) - 1)) - 1) * 100
                return self._apply_thresholds(cagr, dim)
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_revenue_cagr(self, dim) -> tuple[float, str]:
        """营收增速: 近3年营收CAGR。"""
        try:
            inc = self._bundle.income.sort_values("end_date", ascending=False)
            annual = inc[inc["end_date"].astype(str).str.endswith("1231")].head(3)
            revenues = [float(r.get("total_revenue") or 0) for _, r in annual.iterrows()]
            revenues = [r for r in revenues if r > 0]
            if len(revenues) >= 2 and revenues[-1] > 0:
                cagr = ((revenues[0] / revenues[-1]) ** (1 / (len(revenues) - 1)) - 1) * 100
                return self._apply_thresholds(cagr, dim)
        except Exception:
            pass
        return 0, "数据不足"

    # ═══════════════════════════════════════════════════
    # 资本纪律组 (2维)
    # ═══════════════════════════════════════════════════

    def _eval_dividend_consistency(self, dim) -> tuple[float, str]:
        """分红持续性: 近5年每年payout≥30%且均值≥40%。"""
        try:
            div_df = self._bundle.dividend
            income_df = self._bundle.income

            # 汇总每年已实施分红总额
            annual_divs: dict[int, float] = {}
            if not div_df.empty and "end_date" in div_df.columns:
                for _, row in div_df.iterrows():
                    proc = str(row.get("div_proc", ""))
                    if proc != "实施":
                        continue
                    year = int(str(row.get("end_date", ""))[:4])
                    cash_per_share = float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))
                    annual_divs[year] = annual_divs.get(year, 0) + cash_per_share

            income_yearly = income_df[
                income_df["end_date"].astype(str).str.endswith("1231")
            ].sort_values("end_date", ascending=False).head(5)

            payout_ratios = []
            for _, row in income_yearly.iterrows():
                year = int(str(row.get("end_date", ""))[:4])
                np_val = float(row.get("n_income") or 0) / 1e4  # 元→万元
                if np_val <= 0 or year not in annual_divs:
                    continue
                total_share = self._get_year_end_total_share(year)
                if total_share <= 0:
                    continue
                total_div = annual_divs[year] * total_share
                payout_ratios.append(total_div / np_val * 100)

            if not payout_ratios:
                return 0, "无分红数据"

            all_above_30 = all(p >= 30 for p in payout_ratios)
            mean_payout = float(np.mean(payout_ratios))

            if all_above_30 and mean_payout >= 40:
                return 2, "持续分钱 (每年≥30%, 均值≥40%)"
            elif mean_payout >= 30:
                return 1, f"有分红 (均值 {mean_payout:.0f}%)"
            else:
                return 0, f"分红不足 (均值 {mean_payout:.0f}%)"
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_share_count_trend(self, dim) -> tuple[float, str]:
        """股本变动: 近5年总股本变化率（v0.26 排除送转股）。"""
        try:
            db = self._bundle.daily_basic.sort_values("trade_date", ascending=False)
            # 找最早和最新的年末数据
            years = sorted(set(str(d).split("T")[0][:4] for d in db["trade_date"]
                               if isinstance(d, str)))
            if len(years) < 2:
                return 0, "数据不足"

            # 只用最近5年
            recent_years = years[-5:]
            latest_year_data = db[
                db["trade_date"].astype(str).str.startswith(recent_years[-1])
            ].head(1)
            earliest_year_data = db[
                db["trade_date"].astype(str).str.startswith(recent_years[0])
            ].tail(1)

            if latest_year_data.empty or earliest_year_data.empty:
                return 0, "数据不足"

            latest_share = float(latest_year_data.iloc[0].get("total_share") or 0)
            earliest_share = float(earliest_year_data.iloc[0].get("total_share") or 0)
            if earliest_share <= 0:
                return 0, "数据不足"

            raw_change_pct = (latest_share / earliest_share - 1) * 100

            # v0.26: 排除送转股影响 — 送股(stk_div)和转增(stk_bo_rate)
            # 这些是利润分配而非融资摊薄，不应扣分
            div_df = self._bundle.dividend
            stk_div_factor = 1.0
            if not div_df.empty and "end_date" in div_df.columns:
                div_copy = div_df.copy()
                div_copy["fiscal_year"] = div_copy["end_date"].astype(str).str[:4]
                # 只取近5年内的已实施送转
                for _, row in div_copy.iterrows():
                    fy = str(row.get("fiscal_year", ""))
                    if fy not in recent_years:
                        continue
                    stk_div = float(row.get("stk_div", 0) or 0)
                    stk_bo = float(row.get("stk_bo_rate", 0) or 0)
                    if stk_div + stk_bo > 0:
                        stk_div_factor *= (1 + stk_div + stk_bo)

            # 有机股本变化 = 总变化 / 送转股因子
            if stk_div_factor > 1.0:
                organic_change_pct = ((latest_share / stk_div_factor) / earliest_share - 1) * 100
            else:
                organic_change_pct = raw_change_pct

            # 如果有送转股且有机变化不大，标注
            if stk_div_factor > 1.01 and abs(organic_change_pct) < 5:
                score, label = self._apply_thresholds(organic_change_pct, dim)
                return score, f"{label} (送转股已排除, 有机变化={organic_change_pct:.1f}%)"

            return self._apply_thresholds(organic_change_pct, dim)
        except Exception:
            pass
        return 0, "数据不足"

    # ═══════════════════════════════════════════════════
    # 治理组 (2维)
    # ═══════════════════════════════════════════════════

    def _eval_management_stability(self, dim) -> tuple[float, str]:
        """管理层稳定性: 默认数据不可获取得1分。"""
        # Tushare 无直接管理层更换数据，默认给 1 分
        return 1, "数据不足（默认中性）"

    def _eval_earnings_authenticity(self, dim) -> tuple[float, str]:
        """盈利真实性: 近3年经营CF/净利润最小值。"""
        try:
            cf = self._bundle.cashflow.sort_values("end_date", ascending=False)
            inc = self._bundle.income.sort_values("end_date", ascending=False)

            cf_annual = cf[cf["end_date"].astype(str).str.endswith("1231")].head(3)
            inc_annual = inc[inc["end_date"].astype(str).str.endswith("1231")].head(3)

            ratios = []
            for _, crow in cf_annual.iterrows():
                op_cf = float(crow.get("n_cashflow_act") or 0)
                ed = str(crow.get("end_date", ""))
                n_income = 0
                for _, irow in inc_annual.iterrows():
                    if str(irow.get("end_date", "")) == ed:
                        n_income = float(irow.get("n_income") or 0) / 1e4  # 元→万元
                        break
                if n_income and n_income > 0:
                    ratios.append(op_cf / n_income)  # op_cf is also in 万元

            if ratios:
                min_ratio = min(ratios)
                return self._apply_thresholds(min_ratio, dim)
        except Exception:
            pass
        return 0, "数据不足"

    # ═══════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════

    def _get_latest_annual_roe(self) -> float:
        """获取最近年报的ROE（含年化逻辑）。"""
        fi = self._bundle.fina_indicator
        annual = fi[fi["end_date"].astype(str).str.endswith("1231")].head(1)
        if not annual.empty:
            return float(annual.iloc[0].get("roe") or 0)
        # 无年报：取最新季报年化
        latest = fi.head(1)
        if latest.empty:
            return 0
        roe_raw = float(latest.iloc[0].get("roe") or 0)
        try:
            end_str = str(latest.iloc[0].get("end_date", "")).strip()
            month = int(end_str[4:6]) if len(end_str) >= 6 else 12
        except (ValueError, IndexError):
            month = 12

        if month in (3, 4):
            return roe_raw * 4.0
        elif month in (6, 7, 8):
            return roe_raw * 2.0
        elif month in (9, 10):
            return roe_raw * (4.0 / 3.0)
        return roe_raw

    def _compute_roic(self) -> float | None:
        """计算ROIC = NOPAT / Invested Capital。"""
        try:
            bs = self._bundle.balancesheet.sort_values("end_date", ascending=False)
            bs_annual = bs[bs["end_date"].astype(str).str.endswith("1231")].head(1)
            inc = self._bundle.income.sort_values("end_date", ascending=False)
            inc_annual = inc[inc["end_date"].astype(str).str.endswith("1231")].head(1)

            if bs_annual.empty or inc_annual.empty:
                return None

            bs_row = bs_annual.iloc[0]
            inc_row = inc_annual.iloc[0]

            # NOPAT = EBIT × (1 - tax_rate)
            # EBIT ≈ total_profit + interest_expense (简化为财务费用)
            total_profit = float(inc_row.get("total_profit") or 0) / 1e4  # 元→万元
            fin_exp = float(inc_row.get("fin_exp") or 0) / 1e4
            ebit = total_profit + abs(fin_exp)  # fin_exp is typically negative
            nopat = ebit * (1 - self._tax_rate)

            # Invested Capital = 权益 + 有息负债 - 超额现金
            equity = float(bs_row.get("total_hldr_eqy_exc_min_int") or 0)
            st_borrow = float(bs_row.get("st_borrow") or 0)
            lt_borrow = float(bs_row.get("lt_borrow") or 0)
            bonds = float(bs_row.get("bonds_payable") or 0)
            currency = float(bs_row.get("money_cap") or 0)

            interest_debt = abs(st_borrow) + abs(lt_borrow) + abs(bonds)
            excess_cash = max(0, currency - st_borrow * 0.1)
            invested_capital = equity + interest_debt - excess_cash

            if invested_capital <= 0:
                return None

            return round(nopat / invested_capital * 100, 2)
        except Exception:
            return None

    def _get_year_end_total_share(self, year: int) -> float:
        """获取年末总股本（万股）。"""
        try:
            end_date = f"{year}1231"
            db = self._bundle.daily_basic
            row = db[db["trade_date"].astype(str) == end_date]
            if not row.empty:
                ts = row.iloc[0].get("total_share")
                if ts and float(ts) > 0:
                    return float(ts)
        except Exception:
            pass

        # fallback: 往前找
        for day_offset in range(1, 15):
            try:
                day = 31 - day_offset
                if day < 1:
                    break
                alt = f"{year}12{day:02d}"
                db = self._bundle.daily_basic
                row = db[db["trade_date"].astype(str) == alt]
                if not row.empty:
                    ts = row.iloc[0].get("total_share")
                    if ts and float(ts) > 0:
                        return float(ts)
            except Exception:
                continue
        return 0.0

    @staticmethod
    def _apply_thresholds(value: float, dim) -> tuple[float, str]:
        """对数值型维度应用阈值。"""
        for t in dim.thresholds:
            t_min = t.min
            t_max = t.max
            score = t.score or 0
            label = t.label or ""

            if t_min is not None and t_max is not None:
                if t_min <= value <= t_max:
                    return score, label
            elif t_min is not None and t_max is None:
                if value >= t_min:
                    return score, label
            elif t_min is None and t_max is not None:
                if value <= t_max:
                    return score, label
        return 0, "未匹配"
