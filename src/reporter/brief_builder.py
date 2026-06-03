"""
简报组装器 — 从 StockDataBundle + FinalScore 提取趋势和快照，组装 context dict。

区域 A: 核心数据趋势 (4 张表)
  表A1. 三大报表（合并视图）  单位：亿元
  表A2. 财务指标              单位：%
  表A3. 估值快照              混合
  表A4. 分红记录              元/股

区域 B: 管线计算表格 (5 张表)
  表B1. HardGate 否决检查
  表B2. L2 初筛
  表B3. L3 商业模式十二维
  表B4. L4 穿透回报率
  表B5. L5 安全边际

所有货币量统一为「亿元」。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.calculator.turtle_strategy.scoring import FinalScore
from src.data_pool.bundle import StockDataBundle
from src.reporter.unit_converter import to_yi, safe_yearly_trend, safe_latest


def _safe_fmt(v: Any, decimals: int = 2) -> str:
    """安全格式化数值。"""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


class BriefBuilder:
    """简报组装器。

    Usage:
        builder = BriefBuilder(bundle, final_score)
        context = builder.build()
    """

    def __init__(self, bundle: StockDataBundle, final_score: FinalScore):
        self._b = bundle
        self._f = final_score

    def build(self) -> dict[str, Any]:
        """组装完整 context dict，供 Jinja2 模板使用。"""
        return {
            # ── 基础信息 ──
            "name": self._f.name or self._f.ts_code,
            "ts_code": self._f.ts_code,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),

            # ── 打分概览 ──
            "final_score": _safe_fmt(self._f.final_score, 2),
            "pool": self._f.pool,
            "l2_score": _safe_fmt(self._f.l2_score, 1),
            "l3_score": _safe_fmt(self._f.l3_score, 1),
            "l4_score": _safe_fmt(self._f.l4_score, 1),
            "l5_score": _safe_fmt(self._f.l5_score, 1),

            # ── 区域 A: 核心数据趋势 ──
            "table_a1_financials": self._build_a1_financials(),
            "table_a2_indicators": self._build_a2_indicators(),
            "table_a3_valuation": self._build_a3_valuation(),
            "table_a4_dividend": self._build_a4_dividend(),

            # ── 区域 B: 管线计算表格 ──
            "table_b1_hardgate": self._build_b1_hardgate(),
            "table_b2_l2": self._build_b2_l2(),
            "table_b3_l3": self._build_b3_l3(),
            "table_b4_l4": self._build_b4_l4(),
            "table_b5_l5": self._build_b5_l5(),
        }

    # ═══════════════════════════════════════════
    # 区域 A: 核心数据趋势
    # ═══════════════════════════════════════════

    def _build_a1_financials(self) -> dict[str, Any]:
        """表A1. 三大报表关键行合并视图 单位：亿元。"""
        # 整合 cashflow / income / balancesheet 的关键字段
        fields_cf = ["n_cashflow_act", "c_pay_acq_const_fiolta", "c_pay_acq_subsidiary"]
        fields_inc = ["total_revenue", "n_income", "total_profit", "fin_exp"]
        fields_bs = ["money_cap", "total_assets", "total_liab", "st_borrow", "long_term_equity_invest"]

        labels = {
            "n_cashflow_act": "经营现金流",
            "c_pay_acq_const_fiolta": "资本支出",
            "c_pay_acq_subsidiary": "取得子公司现金",
            "total_revenue": "营业收入",
            "n_income": "净利润",
            "total_profit": "利润总额",
            "fin_exp": "财务费用",
            "money_cap": "货币资金",
            "total_assets": "总资产",
            "total_liab": "总负债",
            "st_borrow": "短期借款",
            "long_term_equity_invest": "长期股权投资",
        }

        # 从各表按 end_date 取年末数据
        def _yearly_trend(df, fields_list):
            if df is None or df.empty or "end_date" not in df.columns:
                return {}
            d = df[df["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False).head(5)
            years = [str(r["end_date"])[:4] for _, r in d.iterrows()]
            result = {f: [] for f in fields_list}
            for _, row in d.iterrows():
                for f in fields_list:
                    raw = float(row.get(f, 0) or 0)
                    result[f].append(to_yi(raw, f))
            return {"years": years, "data": result}

        cf_trend = _yearly_trend(self._b.cashflow, fields_cf)
        inc_trend = _yearly_trend(self._b.income, fields_inc)
        bs_trend = _yearly_trend(self._b.balancesheet, fields_bs)

        # 合并 years（取最长）
        all_years = cf_trend.get("years", inc_trend.get("years", bs_trend.get("years", [])))

        # 按年份索引合并
        columns = []
        for f in fields_cf + fields_inc + fields_bs:
            columns.append({"field": f, "label": labels.get(f, f)})

        rows = []
        for i, yr in enumerate(all_years):
            row_data = {"year": yr}
            for f in fields_cf:
                vals = cf_trend.get("data", {}).get(f, [])
                row_data[f] = _safe_fmt(vals[i], 2) if i < len(vals) else "-"
            for f in fields_inc:
                vals = inc_trend.get("data", {}).get(f, [])
                row_data[f] = _safe_fmt(vals[i], 2) if i < len(vals) else "-"
            for f in fields_bs:
                vals = bs_trend.get("data", {}).get(f, [])
                row_data[f] = _safe_fmt(vals[i], 2) if i < len(vals) else "-"
            rows.append(row_data)

        return {"columns": columns, "rows": rows}

    def _build_a2_indicators(self) -> dict[str, Any]:
        """表A2. 财务指标 单位：%。"""
        fi = self._b.fina_indicator
        if fi is None or fi.empty:
            return {"years": [], "rows": []}

        fields = ["roe", "grossprofit_margin", "debt_to_assets"]
        labels = {"roe": "净资产收益率", "grossprofit_margin": "毛利率", "debt_to_assets": "资产负债率"}

        df = fi[fi["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False).head(5)

        rows = []
        years = []
        for _, row in df.iterrows():
            yr = str(row["end_date"])[:4]
            years.append(yr)
            r = {"year": yr}
            for f in fields:
                raw = float(row.get(f, 0) or 0)
                r[f] = f"{raw:.1f}%"
            rows.append(r)

        columns = [{"field": f, "label": lbl} for f, lbl in labels.items()]
        return {"years": years, "columns": columns, "rows": rows}

    def _build_a3_valuation(self) -> dict[str, Any]:
        """表A3. 估值快照（最新交易日）。"""
        db = self._b.daily_basic
        if db is None or db.empty:
            return {}

        latest = db.sort_values("trade_date", ascending=False).iloc[0]
        trade_date = str(latest.get("trade_date", ""))

        return {
            "trade_date": trade_date,
            "total_mv": _safe_fmt(to_yi(float(latest.get("total_mv") or 0), "total_mv"), 2),
            "pe": _safe_fmt(float(latest.get("pe") or 0), 1),
            "pb": _safe_fmt(float(latest.get("pb") or 0), 1),
            "ps": _safe_fmt(float(latest.get("ps") or 0), 1),
            "dv_ratio": _safe_fmt(float(latest.get("dv_ratio") or 0), 2),
            "turnover_rate": _safe_fmt(float(latest.get("turnover_rate") or 0), 3),
        }

    def _build_a4_dividend(self) -> dict[str, Any]:
        """表A4. 分红记录。"""
        div = self._b.dividend
        if div is None or div.empty:
            return {"rows": []}

        df = div[div["div_proc"].astype(str) == "实施"].sort_values("end_date", ascending=False).head(5)

        rows = []
        for _, row in df.iterrows():
            rows.append({
                "year": str(row.get("end_date", ""))[:4],
                "cash_div": _safe_fmt(float(row.get("cash_div") or 0), 2),
                "cash_div_tax": _safe_fmt(float(row.get("cash_div_tax") or 0), 2),
                "div_proc": str(row.get("div_proc", "")),
            })

        return {"rows": rows}

    # ═══════════════════════════════════════════
    # 区域 B: 管线计算表格
    # ═══════════════════════════════════════════

    def _build_b1_hardgate(self) -> dict[str, Any]:
        """表B1. HardGate 否决检查。"""
        checks = self._f.hard_gate_checks
        items = []
        for c in checks if checks else []:
            items.append({
                "name": c.get("name", ""),
                "value": str(c.get("value", "")),
                "passed": c.get("passed", True),
            })
        return {"passed": self._f.hard_gate_passed, "items": items}

    def _build_b2_l2(self) -> dict[str, Any]:
        """表B2. L2 初筛。"""
        details = self._f.l2_details or {}
        # 从 bundle 补充原始数据
        fi = self._b.fina_indicator
        db = self._b.daily_basic

        latest_fi = fi[fi["end_date"].astype(str).str.endswith("1231")].head(1) if fi is not None and not fi.empty else None
        latest_db = db.sort_values("trade_date", ascending=False).head(1) if db is not None and not db.empty else None

        def _fi_val(field):
            if latest_fi is not None and not latest_fi.empty:
                raw = float(latest_fi.iloc[0].get(field) or 0)
                return f"{raw:.1f}%"
            return "-"

        def _db_val(field, suffix="", decimals=1):
            if latest_db is not None and not latest_db.empty:
                raw = float(latest_db.iloc[0].get(field) or 0)
                return f"{raw:.{decimals}f}{suffix}"
            return "-"

        rows = [
            {"dim": "财务质量", "metric": "净资产收益率", "value": _fi_val("roe"),
             "score": details.get("financial_quality", "-"), "max": 9},
            {"dim": "财务质量", "metric": "毛利率", "value": _fi_val("grossprofit_margin"),
             "score": "-", "max": ""},
            {"dim": "财务质量", "metric": "资产负债率", "value": _fi_val("debt_to_assets"),
             "score": "-", "max": ""},
            {"dim": "估值", "metric": "市盈率", "value": _db_val("pe", "倍"),
             "score": details.get("valuation", "-"), "max": 6},
            {"dim": "估值", "metric": "市净率", "value": _db_val("pb", "倍"),
             "score": "-", "max": ""},
            {"dim": "估值", "metric": "市销率", "value": _db_val("ps", "倍"),
             "score": "-", "max": ""},
            {"dim": "流动性", "metric": "股息率", "value": _db_val("dv_ratio", "%", 2),
             "score": details.get("liquidity", "-"), "max": 3},
            {"dim": "流动性", "metric": "换手率", "value": _db_val("turnover_rate", "%", 3),
             "score": "-", "max": ""},
            {"dim": "加分", "metric": "沪深港通/上市>10年", "value": "是" if self._b.industry else "-",
             "score": details.get("bonus", "-"), "max": 2},
        ]

        return {
            "total": _safe_fmt(self._f.l2_score, 1),
            "max": 20,
            "pool": self._f.l2_pool,
            "rows": rows,
        }

    def _build_b3_l3(self) -> dict[str, Any]:
        """表B3. L3 商业模式十二维。"""
        dim_scores = self._f.l3_dim_scores or {}
        rows = []
        for dim_id, info in dim_scores.items():
            rows.append({
                "group": info.get("group", ""),
                "name": info.get("name", ""),
                "label": info.get("label", ""),
                "score": _safe_fmt(info.get("score", 0), 0),
                "max": 2,
            })

        group_scores = {}
        for r in rows:
            g = r["group"]
            if g not in group_scores:
                group_scores[g] = {"total": 0, "count": 0}
            group_scores[g]["total"] += float(r["score"]) if r["score"] != "-" else 0
            group_scores[g]["count"] += 1

        return {
            "total_dim": _safe_fmt(self._f.l3_total_dim, 1),
            "max_dim": 24,
            "l3_score": _safe_fmt(self._f.l3_score, 1),
            "max_score": 30,
            "level": self._f.l3_level,
            "rows": rows,
            "groups": {g: {"name": g, "total": d["total"], "count": d["count"]}
                      for g, d in group_scores.items()},
        }

    def _build_b4_l4(self) -> dict[str, Any]:
        """表B4. L4 穿透回报率。"""
        f = self._f
        # OE 质量检查细节
        oe_path_b_str = ", ".join(
            [f"{to_yi(v, 'n_cashflow_act'):.2f}" for v in (f.oe_path_b_values or [])]
        ) if f.oe_path_b_values else "N/A"

        dc_yi = to_yi(f.pr_disposable_cash, "n_cashflow_act") if f.pr_disposable_cash else 0
        ratio = f.pr_distribution_ratio
        buyback_yi = to_yi(f.pr_buyback_cancellation, "n_cashflow_act") if f.pr_buyback_cancellation else 0
        current_mv_yi = self._a3_current_mv_yi()

        distributable = round(dc_yi * (ratio / 100), 2)
        reasonable_mv_yi = to_yi(f.l5_reasonable_mv, "total_mv") if f.l5_reasonable_mv else 0

        rows = [
            {"step": "可支配现金", "item": "经营现金流(最新)", "value": f"{dc_yi:.2f} 亿",
             "source": "cashflow.n_cashflow_act"},
            {"step": "可支配现金", "item": "股东盈余中位数", "value": f"{to_yi(f.oe_cf_median, 'n_cashflow_act'):.2f} 亿",
             "source": "OE路径B 5年中位数"},
            {"step": "可支配现金", "item": "维持性资本支出系数", "value": f"{f.capex_coefficient:.2f}",
             "source": "行业先验+资产强度三因子"},
            {"step": "分配比率", "item": "来源",
             "value": "公告承诺" if "tier1" in str(f.pr_distribution_source) else "历史外推",
             "source": "dividend + income"},
            {"step": "分配比率", "item": "分配比率", "value": f"{ratio:.1f}%",
             "source": "5年平均(分红/净利润)" if "tier2" in str(f.pr_distribution_source) else "公告承诺"},
            {"step": "回购注销", "item": "回购注销金额", "value": f"{buyback_yi:.2f} 亿",
             "source": "Web+LLM / Tushare repurchase"},
            {"step": "当前市值", "item": "总市值", "value": f"{current_mv_yi:.2f} 亿",
             "source": "daily_basic.total_mv"},
            {"step": "PR计算", "item": "可分配现金", "value": f"{distributable:.2f} 亿",
             "source": f"{dc_yi:.2f} × {ratio:.1f}%"},
            {"step": "PR计算", "item": "穿透回报率", "value": f"{f.pr_pct:.2f}%",
             "source": f"({distributable:.2f} + {buyback_yi:.2f}) / {current_mv_yi:.2f}"},
            {"step": "质量验证", "item": "股东盈余/净利润", "value": f"{f.oe_cv:.2f}" if f.oe_cv else "N/A",
             "source": "OE路径B 5年"},
            {"step": "质量验证", "item": "股东盈余稳定性(变异系数)", "value": f"{f.oe_cv:.2f}",
             "source": "OE路径B 5年"},
            {"step": "质量验证", "item": "股东盈余趋势(3年复合)", "value": f"{f.oe_cagr:.1f}%",
             "source": "OE路径B 近3年"},
            {"step": "质量", "item": "质量标签", "value": f.oe_quality, "source": ""},
            {"step": "L4得分", "item": "起点分", "value": _safe_fmt(f.pr_starting_score, 1),
             "source": f"PR={f.pr_pct:.2f}%"},
            {"step": "L4得分", "item": "质量扣分", "value": _safe_fmt(f.pr_quality_penalty, 1), "source": ""},
            {"step": "L4得分", "item": "L4最终得分", "value": f"{_safe_fmt(f.l4_score, 1)} / 45", "source": ""},
        ]

        return {"pr_pct": _safe_fmt(f.pr_pct, 2), "rows": rows}

    def _build_b5_l5(self) -> dict[str, Any]:
        """表B5. L5 安全边际。"""
        f = self._f
        current_mv_yi = self._a3_current_mv_yi()
        reasonable_mv_yi = to_yi(f.l5_reasonable_mv, "total_mv") if f.l5_reasonable_mv else 0
        discount_rate = 7.0

        # 下行缓冲明细
        downside = f.l5_downside_details or []

        rows = [
            {"component": "估值安全", "item": "当前总市值", "value": f"{current_mv_yi:.2f} 亿", "score": "-"},
            {"component": "估值安全", "item": "合理市值(折现率7%)", "value": f"{reasonable_mv_yi:.2f} 亿", "score": "-"},
            {"component": "估值安全", "item": "安全边际率",
             "value": f"{_safe_fmt(f.l5_safety_margin_pct, 1)}%",
             "score": f"{_safe_fmt(f.l5_valuation_score, 1)} / 15"},
        ]

        for d in downside:
            rows.append({
                "component": "下行缓冲",
                "item": d.get("name", ""),
                "value": d.get("label", ""),
                "score": _safe_fmt(d.get("score", 0), 1),
            })

        rows.append({
            "component": "仓位矩阵",
            "item": "仓位上限",
            "value": f"{_safe_fmt(f.position_pct, 1)}%",
            "score": f"{_safe_fmt(f.l5_position_score, 1)} / 5",
        })

        # 汇总
        rows.append({
            "component": "合计",
            "item": "L5 最终得分",
            "value": "",
            "score": f"{_safe_fmt(f.l5_score, 1)} / 25",
        })

        return {
            "safety_margin_pct": _safe_fmt(f.l5_safety_margin_pct, 1),
            "discount_rate": f"{discount_rate:.0f}%",
            "rows": rows,
        }

    # ── 辅助方法 ──

    def _a3_current_mv_yi(self) -> float:
        """获取当前总市值(亿元)。"""
        db = self._b.daily_basic
        if db is None or db.empty:
            return 0.0
        latest = db.sort_values("trade_date", ascending=False).iloc[0]
        return to_yi(float(latest.get("total_mv") or 0), "total_mv")


__all__ = ["BriefBuilder"]
