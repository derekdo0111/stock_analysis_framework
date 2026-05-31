"""
L5 安全边际计算 — 外推可行度(6维) + 价值陷阱(5项) + 3×3仓位矩阵。

L5 = (仓位上限% / 15%) × 25，上限25pt
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.data_fetcher.tushare_client import TushareClient
from src.rules.loader import load_rules


@dataclass
class L5Result:
    """L5 安全边际计算结果。"""
    ts_code: str

    # 外推可行度
    extrapolation_dims: dict[str, float] = field(default_factory=dict)
    extrapolation_total: float = 0.0
    extrapolation_level: str = ""

    # 价值陷阱
    traps_triggered: list[str] = field(default_factory=list)
    trap_score: int = 0
    trap_level: str = ""

    # 仓位矩阵
    position_pct: float = 0.0
    position_label: str = ""

    # L5 得分
    l5_score: float = 0.0
    l5_max: float = 25.0


class L5Calculator:
    """L5 安全边际计算器。"""

    def __init__(self, client: TushareClient):
        self._client = client
        self._rules = load_rules()
        self._mos = self._rules.turtle_constants.margin_of_safety

    def calculate(self, ts_code: str, industry: str = "") -> L5Result:
        result = L5Result(ts_code=ts_code)

        # 1. 外推可行度 6维评分
        self._calc_extrapolation(ts_code, industry, result)

        # 2. 价值陷阱 5项+2子触发
        self._calc_value_traps(ts_code, result)

        # 3. 3×3 仓位矩阵
        self._lookup_position(result)

        # 4. L5 得分
        result.l5_score = round(min(self._mos.max_score, (result.position_pct / 15.0) * self._mos.max_score), 2)

        return result

    def _calc_extrapolation(self, ts_code: str, industry: str, result: L5Result) -> None:
        dims = self._mos.extrapolation.dimensions
        scores: dict[str, float] = {}

        for dim in dims:
            dim_id = dim.id
            try:
                if dim_id == "revenue_stability":
                    scores[dim_id] = self._score_revenue_stability(ts_code, dim)
                elif dim_id == "margin_stability":
                    scores[dim_id] = self._score_margin_stability(ts_code, dim)
                elif dim_id == "roe_stability":
                    scores[dim_id] = self._score_roe_stability(ts_code, dim)
                elif dim_id == "industry_predictability":
                    scores[dim_id] = self._score_industry_predictability(industry, dim)
                elif dim_id == "management_stability":
                    scores[dim_id] = self._score_management_stability(ts_code, dim)
                elif dim_id == "oe_growth_trend":
                    scores[dim_id] = self._score_oe_growth(ts_code, dim)
            except Exception:
                scores[dim_id] = 2  # default mid score

        result.extrapolation_dims = scores
        result.extrapolation_total = round(sum(scores.values()), 1)

        # 分级
        levels = self._mos.extrapolation.levels
        for level_name, level in levels.items():
            if level_name == "high" and result.extrapolation_total >= (level.min or 0):
                result.extrapolation_level = "高可行"
            elif level_name == "medium" and (level.min or 0) <= result.extrapolation_total <= (level.max or 999):
                result.extrapolation_level = "中可行"
            elif level_name == "low" and result.extrapolation_total <= (level.max or 999):
                result.extrapolation_level = "低可行"

    def _calc_value_traps(self, ts_code: str, result: L5Result) -> None:
        items = self._mos.value_trap_checks.items
        triggered: list[str] = []
        extra = 0

        for item in items:
            item_id = item.id

            # 1. 盈利真实性
            if item_id == 1:
                if self._check_cf_to_profit(ts_code):
                    triggered.append(item.name)
            # 2. 资产质量
            elif item_id == 2:
                if self._check_asset_quality(ts_code):
                    triggered.append(item.name)
            # 3. 负债压力
            elif item_id == 3:
                is_triggered, sub_extra = self._check_debt_pressure(ts_code, item)
                if is_triggered:
                    triggered.append(item.name)
                extra += sub_extra
            # 4. 行业趋势
            elif item_id == 4:
                if self._check_industry_trend(ts_code):
                    triggered.append(item.name)
            # 5. 治理风险
            elif item_id == 5:
                if self._check_governance(ts_code):
                    triggered.append(item.name)

        result.traps_triggered = triggered
        result.trap_score = len(triggered) + extra

        # 分级
        levels = self._mos.value_trap_checks.levels
        for level_name, level in levels.items():
            if level_name == "low" and result.trap_score <= (level.max or 0):
                result.trap_level = "低风险"
            elif level_name == "medium" and (level.min or 0) <= result.trap_score <= (level.max or 0):
                result.trap_level = "中风险"
            elif level_name == "high" and result.trap_score >= (level.min or 0):
                result.trap_level = "高风险"

    def _lookup_position(self, result: L5Result) -> None:
        e = result.extrapolation_level.replace("可行", "").lower() if result.extrapolation_level else "medium"
        t = result.trap_level.replace("风险", "").lower() if result.trap_level else "low"

        e_map = {"高": "high", "中": "medium", "低": "low"}
        t_map = {"低": "low", "中": "medium", "高": "high"}

        e_key = e_map.get(e, "medium")
        t_key = t_map.get(t, "low")
        matrix_key = f"{e_key}_extrapolation_{t_key}_trap"

        pm = self._mos.position_matrix
        if matrix_key in pm:
            result.position_pct = pm[matrix_key].position_pct
            result.position_label = pm[matrix_key].label

    # ── 各维度评分实现 ──────────────────────────────────────

    def _score_revenue_stability(self, ts_code: str, dim) -> float:
        try:
            df = self._client.income(ts_code=ts_code).sort_values("end_date", ascending=False).head(5)
            revenues = [float(r.get("total_revenue") or 0) for _, r in df.iterrows() if r.get("total_revenue")]
            if len(revenues) >= 3:
                growth_rates = [(revenues[i] - revenues[i + 1]) / revenues[i + 1] * 100
                                for i in range(len(revenues) - 1) if revenues[i + 1] > 0]
                std = float(np.std(growth_rates)) if growth_rates else 50
                return self._apply_dim_thresholds(std, dim)
        except Exception:
            pass
        return 2

    def _score_margin_stability(self, ts_code: str, dim) -> float:
        try:
            df = self._client.fina_indicator(ts_code=ts_code).sort_values("end_date", ascending=False).head(5)
            margins = [float(r.get("grossprofit_margin") or 0) for _, r in df.iterrows()]
            if margins:
                std = float(np.std(margins))
                return self._apply_dim_thresholds(std, dim)
        except Exception:
            pass
        return 2

    def _score_roe_stability(self, ts_code: str, dim) -> float:
        try:
            df = self._client.fina_indicator(ts_code=ts_code).sort_values("end_date", ascending=False).head(5)
            roes = [float(r.get("roe") or 0) for _, r in df.iterrows()]
            if roes:
                std = float(np.std(roes))
                return self._apply_dim_thresholds(std, dim)
        except Exception:
            pass
        return 2

    def _score_industry_predictability(self, industry: str, dim) -> float:
        scoring = dim.scoring
        if isinstance(scoring, dict):
            for kw, score in scoring.items():
                if kw in industry:
                    return float(score)
            return float(scoring.get("default", 3))
        return 3

    def _score_management_stability(self, ts_code: str, dim) -> float:
        # Tushare 无直接管理层更换数据 → 默认 3 分
        return 3

    def _score_oe_growth(self, ts_code: str, dim) -> float:
        try:
            df = self._client.cashflow(ts_code=ts_code).sort_values("end_date", ascending=False).head(5)
            # 用简易OE估计: op_cf - capex
            oe_vals = []
            for _, r in df.iterrows():
                op_cf = r.get("n_cashflow_act") or 0
                capex = r.get("c_pay_acq_const_fiolta") or 0
                oe_vals.append(op_cf - capex * 0.55)  # 默认系数
            if len(oe_vals) >= 3 and oe_vals[-1] and oe_vals[-1] != 0:
                cagr = (oe_vals[0] / oe_vals[-1]) ** (1 / 3) - 1
                return self._apply_dim_thresholds(cagr * 100, dim)
        except Exception:
            pass
        return 2

    # ── 价值陷阱检查 ──────────────────────────────────────

    def _check_cf_to_profit(self, ts_code: str) -> bool:
        try:
            cf = self._client.cashflow(ts_code=ts_code).sort_values("end_date", ascending=False).head(3)
            inc = self._client.income(ts_code=ts_code).sort_values("end_date", ascending=False).head(3)
            for _, crow in cf.iterrows():
                op_cf = crow.get("n_cashflow_act") or 0
                ed = str(crow.get("end_date", ""))
                n_income = 0
                for _, irow in inc.iterrows():
                    if str(irow.get("end_date", "")) == ed:
                        n_income = irow.get("n_income") or 0
                        break
                if n_income and n_income != 0 and op_cf / n_income < 0.6:
                    return True
        except Exception:
            pass
        return False

    def _check_asset_quality(self, ts_code: str) -> bool:
        try:
            bs = self._client.balancesheet(ts_code=ts_code).sort_values("end_date", ascending=False).head(3)
            inc = self._client.income(ts_code=ts_code).sort_values("end_date", ascending=False).head(3)
            # 应收增速 vs 营收增速
            if len(bs) >= 2 and len(inc) >= 2:
                ar_growth = (bs.iloc[0].get("accounts_receiv") or 0) / max(1, (bs.iloc[-1].get("accounts_receiv") or 1)) - 1
                rev_growth = (inc.iloc[0].get("total_revenue") or 0) / max(1, (inc.iloc[-1].get("total_revenue") or 1)) - 1
                if ar_growth > rev_growth * 1.5:
                    return True
                inv_growth = (bs.iloc[0].get("inventories") or 0) / max(1, (bs.iloc[-1].get("inventories") or 1)) - 1
                if inv_growth > rev_growth * 1.3:
                    return True
        except Exception:
            pass
        return False

    def _check_debt_pressure(self, ts_code: str, item) -> tuple[bool, int]:
        extra = 0
        try:
            fi = self._client.fina_indicator(ts_code=ts_code).head(1)
            if not fi.empty:
                cr = float(fi.iloc[0].get("current_ratio") or 1.0)
                qr = float(fi.iloc[0].get("quick_ratio") or 0.5)
                if cr < 1.0 or qr < 0.5:
                    # 子触发
                    for st in item.sub_triggers:
                        st_name = st.get("name", "")
                        if "高杠杆" in st_name:
                            try:
                                bs = self._client.balancesheet(ts_code=ts_code).head(1)
                                cf = self._client.cashflow(ts_code=ts_code).head(1)
                                if not bs.empty and not cf.empty:
                                    debt = (bs.iloc[0].get("st_borrow") or 0) + (bs.iloc[0].get("lt_borrow") or 0) + (bs.iloc[0].get("bonds_payable") or 0)
                                    # EBITDA ≈ n_income + taxes + interest + depreciation
                                    inc = self._client.income(ts_code=ts_code).head(1)
                                    ebitda = (inc.iloc[0].get("total_profit") or 0) + debt * 0.04
                                    if ebitda and ebitda > 0 and debt / ebitda > 4:
                                        extra += 1
                            except Exception:
                                pass
                        if "利息覆盖" in st_name:
                            if cr < 1.0:
                                extra += 1
                    return True, extra
        except Exception:
            pass
        return False, extra

    def _check_industry_trend(self, ts_code: str) -> bool:
        # GDP ≈ 5%, threshold = 5-2 = 3%
        try:
            inc = self._client.income(ts_code=ts_code).sort_values("end_date", ascending=False).head(3)
            if len(inc) >= 3:
                revenues = [float(r.get("total_revenue") or 0) for _, r in inc.iterrows()]
                if revenues[0] and revenues[-1] and revenues[-1] > 0:
                    cagr = (revenues[0] / revenues[-1]) ** (1 / 3) - 1
                    if cagr < 0.03:  # GDP-2%
                        return True
        except Exception:
            pass
        return False

    def _check_governance(self, ts_code: str) -> bool:
        # 大股东质押率需要 pledge_stat 接口
        try:
            df = self._client.pledge_stat(ts_code=ts_code)
            if not df.empty:
                pledge_ratio = float(df.iloc[0].get("pledge_ratio") or 0)
                if pledge_ratio > 50:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _apply_dim_thresholds(value: float, dim) -> float:
        for t in dim.scoring:
            min_v = t.get("min")
            max_v = t.get("max")
            score = t.get("score", 0) or t.get("penalty", 0)
            if min_v is not None and max_v is not None:
                if min_v <= value < max_v:
                    return score
            elif min_v is not None and max_v is None:
                if value >= min_v:
                    return score
            elif min_v is None and max_v is not None:
                if value <= max_v:
                    return score
        return 1
