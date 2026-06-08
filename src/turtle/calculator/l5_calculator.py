"""
L5 安全边际计算 — v0.23 纯估值保护。

三组件:
1. 估值安全边际率 (0-15分): 合理市值 vs 当前市值的折扣
2. 下行风险缓冲   (0-5分):  资产底价 + 股息托底 + 回购支撑
3. 仓位矩阵       (0-5分):  由安全边际率单维驱动

折现率: 7% = max(无风险利率+2%, 5%) + 个股风险溢价2%
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.core.data.pool.bundle import StockDataBundle
from src.turtle.rules.loader import load_rules


@dataclass
class L5Result:
    """L5 安全边际计算结果 — v0.23。"""

    ts_code: str

    # 估值安全边际
    safety_margin_pct: float = 0.0  # 安全边际率(%)
    reasonable_market_cap: float = 0.0  # 合理市值(万元)
    current_market_cap: float = 0.0  # 当前市值(万元)
    valuation_score: float = 0.0  # 0-15
    valuation_label: str = ""

    # 下行缓冲
    downside_buffer_score: float = 0.0  # 0-5
    downside_buffer_details: list[dict] = field(default_factory=list)

    # 仓位
    position_pct: float = 0.0
    position_score: float = 0.0  # 0-5
    position_label: str = ""

    # L5 总分
    l5_score: float = 0.0
    l5_max: float = 25.0


class L5Calculator:
    """L5 估值安全边际计算器 — v0.23。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._rules = load_rules()
        self._mos = self._rules.turtle_constants.margin_of_safety

    def calculate(self, ts_code: str, industry: str = "") -> L5Result:
        result = L5Result(ts_code=ts_code)

        # Step 0: 获取关键数据
        distributable = self._get_distributable_amount()
        current_mv = self._get_current_market_cap(ts_code)
        result.current_market_cap = current_mv

        discount_rate = self._mos.discount_rate

        # Step 1: 估值安全边际率 (0-15分)
        if current_mv > 0 and distributable > 0 and discount_rate > 0:
            result.reasonable_market_cap = distributable / discount_rate
            result.safety_margin_pct = round(
                (result.reasonable_market_cap - current_mv) / current_mv * 100, 2
            )
        result.valuation_score, result.valuation_label = self._score_valuation_safety_margin(
            result.safety_margin_pct
        )

        # Step 2: 下行风险缓冲 (0-5分)
        result.downside_buffer_score, result.downside_buffer_details = self._score_downside_buffer(
            ts_code, current_mv
        )

        # Step 3: 仓位矩阵 (0-5分) — 由安全边际率驱动
        result.position_pct, result.position_score, result.position_label = self._lookup_position(
            result.safety_margin_pct
        )

        # L5 总分
        result.l5_score = round(
            result.valuation_score + result.downside_buffer_score + result.position_score, 2
        )

        return result

    # ── 估值安全边际 ───────────────────────────────────

    def _get_distributable_amount(self) -> float:
        """获取可分配现金（万元）= DC × 分配比率 + 回购注销。"""
        try:
            from src.core.data.pool.schema.disposable_cash import DisposableCashCalculator
            dc_calc = DisposableCashCalculator(self._bundle)
            dc_result = dc_calc.calculate(self._bundle.ts_code)

            # 分配比率（简化版：用历史 mean(分红/NP)）
            ratio = self._estimate_distribution_ratio()
            buyback = self._get_buyback_cancellation_amount()

            return dc_result.current * (ratio / 100) + buyback
        except Exception:
            return 0.0

    def _estimate_distribution_ratio(self) -> float:
        """估算分配比率（降级到二档外推）。"""
        try:
            # 一档：公告承诺
            commitment = getattr(self._bundle, "dividend_commitment", None)
            if commitment and commitment.has_commitment and commitment.ratio:
                return commitment.ratio

            # 二档：历史 mean(分红/NP)
            div_df = self._bundle.dividend
            income_df = self._bundle.income

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
                np_val = float(row.get("n_income") or 0) / 1e4
                if np_val <= 0 or year not in annual_divs:
                    continue
                total_share = self._get_year_end_total_share(year)
                if total_share <= 0:
                    continue
                total_div = annual_divs[year] * total_share
                payout_ratios.append(total_div / np_val * 100)

            if payout_ratios:
                return float(np.mean(payout_ratios))
        except Exception:
            pass
        return 30.0

    def _get_buyback_cancellation_amount(self) -> float:
        """获取回购注销金额。"""
        buyback_info = getattr(self._bundle, "buyback_cancellation", None)
        if buyback_info and buyback_info.has_cancellation and buyback_info.amount > 0:
            return buyback_info.amount

        try:
            df = self._bundle.repurchase
            if df.empty:
                return 0.0
            proc_col = df["proc"].astype(str).str.strip()
            df = df[proc_col.isin(["实施", "完成", "已完成"])].copy()
            if "proc" in df.columns:
                cancel_mask = df["proc"].astype(str).str.contains("注销", na=False)
                if cancel_mask.any() and "amount" in df.columns:
                    return float(df.loc[cancel_mask, "amount"].sum())
        except Exception:
            pass
        return 0.0

    def _get_current_market_cap(self, ts_code: str) -> float:
        """获取最新总市值(万元)。"""
        try:
            db = self._bundle.daily_basic.sort_values("trade_date", ascending=False)
            if not db.empty:
                mv = db.iloc[0].get("total_mv")
                if mv and float(mv) > 0:
                    return float(mv)
        except Exception:
            pass
        return 0.0

    def _score_valuation_safety_margin(self, safety_margin_pct: float) -> tuple[float, str]:
        """根据安全边际率打分 (0-15)。"""
        vsm = self._mos.valuation_safety_margin
        for t in vsm.thresholds:
            t_min = t.min
            t_max = t.max
            score = t.score or 0
            label = t.label or ""
            if t_min is not None and t_max is not None:
                if t_min <= safety_margin_pct < t_max:
                    return score, label
            elif t_min is not None and t_max is None:
                if safety_margin_pct >= t_min:
                    return score, label
            elif t_min is None and t_max is not None:
                if safety_margin_pct < t_max:
                    return score, label
        return 0, "溢价买入"

    # ── 下行风险缓冲 ───────────────────────────────────

    def _score_downside_buffer(self, ts_code: str, current_mv: float) -> tuple[float, list[dict]]:
        """下行风险缓冲评分 (0-5分)。"""
        details: list[dict] = []
        total = 0.0

        db_cfg = self._mos.downside_buffer
        for item in db_cfg.items:
            item_id = item.id
            try:
                if item_id == "asset_floor":
                    s, l = self._eval_asset_floor(current_mv, item)
                elif item_id == "dividend_anchor":
                    s, l = self._eval_dividend_anchor(item)
                elif item_id == "buyback_support":
                    s, l = self._eval_buyback_support(item)
                else:
                    s, l = 0, "未实现"
            except Exception:
                s, l = 0, "计算异常"

            total += s
            details.append({"id": item_id, "name": item.name, "score": s, "label": l})

        return round(total, 1), details

    def _eval_asset_floor(self, current_mv: float, item) -> tuple[float, str]:
        """资产底价: (货币资金+交易金融资产-总负债)/市值 %。
        
        current_mv 来自 daily_basic.total_mv（万元），
        balancesheet 各字段为元，需统一为万元后再计算比率。
        """
        try:
            bs = self._bundle.balancesheet.sort_values("end_date", ascending=False).head(1)
            if bs.empty or current_mv <= 0:
                return 0, "数据不足"
            row = bs.iloc[0]
            money_cap = float(row.get("money_cap") or 0) / 1e4  # 元→万元
            trad_assets = float(row.get("trad_asset") or 0) / 1e4  # 元→万元
            total_liab = float(row.get("total_liab") or 0) / 1e4  # 元→万元
            net_liquid = money_cap + trad_assets - total_liab
            ratio = net_liquid / current_mv * 100
            for t in item.thresholds:
                t_min = t.min
                t_max = t.max
                if t_min is not None and t_max is not None:
                    if t_min <= ratio < t_max:
                        return t.score or 0, t.label or ""
                elif t_min is not None:
                    if ratio >= t_min:
                        return t.score or 0, t.label or ""
                elif t_max is not None:
                    if ratio < t_max:
                        return t.score or 0, t.label or ""
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_dividend_anchor(self, item) -> tuple[float, str]:
        """股息托底: 当前股息率 vs 历史中位数 × 0.8。"""
        try:
            db = self._bundle.daily_basic.sort_values("trade_date", ascending=False)
            if db.empty:
                return 0, "数据不足"

            current_dy = float(db.iloc[0].get("dv_ratio") or 0)
            # 历史中位数（排除最近一年以排除价格波动）
            hist = db.iloc[250:] if len(db) > 250 else db.tail(3)
            hist_dys = [float(r.get("dv_ratio") or 0) for _, r in hist.iterrows() if r.get("dv_ratio")]
            if not hist_dys:
                return 0, "历史数据不足"
            median_dy = float(np.median(hist_dys))

            if median_dy > 0 and current_dy >= median_dy * 0.8:
                return 1, "股息有托底"
            return 0, "股息在低位"
        except Exception:
            pass
        return 0, "数据不足"

    def _eval_buyback_support(self, item) -> tuple[float, str]:
        """回购支撑: 是否存在回购注销。"""
        buyback = self._get_buyback_cancellation_amount()
        if buyback > 0:
            return 2, "有回购注销"
        return 0, "无回购"

    # ── 仓位矩阵 ───────────────────────────────────────

    def _lookup_position(self, safety_margin_pct: float) -> tuple[float, float, str]:
        """由安全边际率确定仓位上限+得分。"""
        pm = self._mos.position_matrix
        for t in pm.thresholds:
            t_min = t.min
            t_max = t.max
            if t_min is not None and t_max is not None:
                if t_min <= safety_margin_pct < t_max:
                    return t.position_pct, t.score, t.label
            elif t_min is not None and t_max is None:
                if safety_margin_pct >= t_min:
                    return t.position_pct, t.score, t.label
            elif t_min is None and t_max is not None:
                if safety_margin_pct < t_max:
                    return t.position_pct, t.score, t.label
        return 0.0, 0.0, "0%"

    # ── 辅助方法 ───────────────────────────────────────

    def _get_year_end_total_share(self, year: int) -> float:
        try:
            db = self._bundle.daily_basic
            row = db[db["trade_date"].astype(str) == f"{year}1231"]
            if not row.empty:
                ts = row.iloc[0].get("total_share")
                if ts and float(ts) > 0:
                    return float(ts)
        except Exception:
            pass
        for day_offset in range(1, 15):
            try:
                day = 31 - day_offset
                if day < 1:
                    break
                db = self._bundle.daily_basic
                row = db[db["trade_date"].astype(str) == f"{year}12{day:02d}"]
                if not row.empty:
                    ts = row.iloc[0].get("total_share")
                    if ts and float(ts) > 0:
                        return float(ts)
            except Exception:
                continue
        return 0.0
