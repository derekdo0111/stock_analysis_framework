"""
brief.md 数据底稿组装器 — v0.27 重构。

拼合 Tushare原始数据 + L2-L5管线得分 + 财报深度分析洞察 + 商业知识检索。

brief.md 是数据档案，作为 LLM 分析 Agent 的输入，不是最终输出品。

结构 (v0.27 五区块):
    # 龟龟策略数据底稿 — {name} ({ts_code})

    ## 一、Tushare 原始数据
    [三大报表关键行 / 财务指标 / 估值快照 / 分红记录]

    ## 二、管线计算得分
    [L2门控 / L3十二维 / L4穿透回报率 / L5安全边际]

    ## 三、财报深度分析洞察
    [7模块结构化输出]

    ## 四、分析报告撰写指引
    [告诉分析Agent如何利用以上数据撰写报告]

    ## 五、LLM 商业知识检索
    [5类商业知识: 商业模式/管理层/行业地位/风险监管/分红回购]

用法:
    from src.reporter.brief_md_builder import BriefMDBuilder
    builder = BriefMDBuilder(bundle, final_score, financial_insights, business_knowledge)
    md_text = builder.build()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.calculator.turtle_strategy.scoring import FinalScore
from src.data_pool.bundle import StockDataBundle


class BriefMDBuilder:
    """brief.md 数据底稿组装器。

    Args:
        bundle: 原始 Tushare 数据载体
        final_score: 管线打分结果
        financial_insights: 财报深度分析结果 (FinancialInsights | None)
        business_knowledge: 商业知识检索结果 (BusinessKnowledgeResult | None)
    """

    def __init__(
        self,
        bundle: StockDataBundle,
        final_score: FinalScore,
        financial_insights: Any = None,
        business_knowledge: Any = None,
    ):
        self._b = bundle
        self._f = final_score
        self._fi = financial_insights
        self._bk = business_knowledge

    # ── Public ──

    def build(self) -> str:
        """组装完整 brief.md 字符串（五区块）。"""
        lines: list[str] = []
        lines.append(f"# 龟龟策略数据底稿 — {self._b.name} ({self._b.ts_code})")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # 一、Tushare 原始数据
        lines.append("## 一、Tushare 原始数据")
        lines.append("")
        lines.extend(self._build_section1_financials())
        lines.extend(self._build_section1_indicators())
        lines.extend(self._build_section1_valuation())
        lines.extend(self._build_section1_dividends())
        lines.append("")

        # 二、管线计算得分
        lines.append("## 二、管线计算得分")
        lines.append("")
        lines.extend(self._build_section2_summary())
        lines.extend(self._build_section2_l3())
        lines.extend(self._build_section2_l4())
        lines.extend(self._build_section2_l5())
        lines.append("")

        # 三、财报深度分析洞察
        lines.extend(self._build_section3_financial_insights())
        lines.append("")

        # 四、分析报告撰写指引 (v0.27 重写)
        lines.extend(self._build_section4_analysis_guidance())
        lines.append("")

        # 五、LLM 商业知识检索 (v0.27 新增)
        lines.extend(self._build_section5_business_knowledge())

        return "\n".join(lines)

    # ── Section 1: Tushare 原始数据 ──

    def _build_section1_financials(self) -> list[str]:
        """三大报表关键行（近5年，亿元）。"""
        lines = ["### 1.1 三大报表关键行 (近5年, 亿元)", ""]

        income = self._b.income
        balance = self._b.balancesheet
        cashflow = self._b.cashflow

        if income.empty:
            lines.append("*(income 数据不可用)*")
            return lines

        # 取最近 5 个年报
        income_sorted = income.sort_values("end_date", ascending=False)
        if "f_ann_date" in income_sorted.columns:
            income_sorted = income_sorted[income_sorted["f_ann_date"].notna()]

        years = []
        rows_data: dict[str, list[str]] = {}

        for _, row in income_sorted.head(5).iterrows():
            end_date = str(row.get("end_date", ""))[:4]
            years.append(end_date)

            # 从 income 取字段
            for field, label in [
                ("revenue", "营业收入"),
                ("n_income", "净利润"),
                ("oper_cost", "营业成本"),
            ]:
                val = row.get(field)
                yi = self._to_yi(val)
                rows_data.setdefault(label, []).append(yi)

        # 从 cashflow 取经营现金流
        if not cashflow.empty:
            cf_sorted = cashflow.sort_values("end_date", ascending=False).head(5)
            for _, row in cf_sorted.iterrows():
                val = row.get("n_cashflow_act")
                yi = self._to_yi(val)
                rows_data.setdefault("经营现金流", []).append(yi)

            # CAPEX
            for _, row in cf_sorted.iterrows():
                val = row.get("c_pay_acq_const_fiolta")
                yi = self._to_yi(val)
                rows_data.setdefault("购建固定资产支出", []).append(yi)

        # 从 balance 取关键行
        if not balance.empty:
            bal_sorted = balance.sort_values("end_date", ascending=False).head(5)
            for field, label in [
                ("money_cap", "货币资金"),
                ("total_assets", "总资产"),
                ("total_liab", "总负债"),
                ("st_borr", "短期借款"),
                ("trad_asset", "交易性金融资产"),
            ]:
                for _, row in bal_sorted.iterrows():
                    val = row.get(field)
                    yi = self._to_yi(val)
                    rows_data.setdefault(label, []).append(yi)

        # 渲染表格
        header = "| 项目 | " + " | ".join(years) + " |"
        sep = "|------|" + "|".join(["------" for _ in years]) + "|"
        lines.append(header)
        lines.append(sep)
        for label, vals in rows_data.items():
            row_str = f"| {label} | " + " | ".join(vals) + " |"
            lines.append(row_str)

        return lines

    def _build_section1_indicators(self) -> list[str]:
        """财务指标（近5年）。"""
        lines = ["", "### 1.2 财务指标 (近5年)", ""]

        ind = self._b.fina_indicator
        if ind.empty:
            lines.append("*(fina_indicator 数据不可用)*")
            return lines

        ind_sorted = ind.sort_values("end_date", ascending=False).head(5)
        years = [str(r.get("end_date", ""))[:4] for _, r in ind_sorted.iterrows()]

        fields = [
            ("roe", "ROE (%)"),
            ("grossprofit_margin", "毛利率 (%)"),
            ("netprofit_margin", "净利率 (%)"),
            ("debt_to_assets", "资产负债率 (%)"),
            ("current_ratio", "流动比率"),
        ]

        header = "| 指标 | " + " | ".join(years) + " |"
        sep = "|------|" + "|".join(["------" for _ in years]) + "|"
        lines.append(header)
        lines.append(sep)

        for field, label in fields:
            vals = []
            for _, row in ind_sorted.iterrows():
                v = row.get(field)
                if v is not None and not (isinstance(v, float) and pd.isna(v)):
                    vals.append(f"{float(v):.1f}")
                else:
                    vals.append("-")
            lines.append(f"| {label} | " + " | ".join(vals) + " |")

        return lines

    def _build_section1_valuation(self) -> list[str]:
        """估值快照（最新交易日）。"""
        lines = ["", "### 1.3 估值快照 (最新交易日)", ""]

        db = self._b.daily_basic
        if db.empty:
            lines.append("*(daily_basic 数据不可用)*")
            return lines

        latest = db.sort_values("trade_date", ascending=False).iloc[0]
        total_mv = self._to_yi(latest.get("total_mv"), source_unit="wan")
        pe = latest.get("pe")
        pb = latest.get("pb")

        lines.append(f"- 总市值: {total_mv} 亿元")
        lines.append(f"- PE(TTM): {self._fmt(pe)}")
        lines.append(f"- PB: {self._fmt(pb)}")

        trade_date = str(latest.get("trade_date", ""))
        lines.append(f"- 交易日: {trade_date}")

        return lines

    def _build_section1_dividends(self) -> list[str]:
        """分红记录（近5年）。"""
        lines = ["", "### 1.4 分红记录 (近5年, 元/股)", ""]

        div = self._b.dividend
        if div.empty:
            lines.append("*(dividend 数据不可用)*")
            return lines

        # 按财务年度汇总
        if "end_date" in div.columns:
            div = div.copy()
            div["fiscal_year"] = div["end_date"].astype(str).str[:4]
            yearly = div.groupby("fiscal_year")["cash_div"].sum().reset_index()
            yearly = yearly.sort_values("fiscal_year", ascending=False).head(5)

            for _, row in yearly.iterrows():
                yr = row["fiscal_year"]
                cash = row["cash_div"]
                lines.append(f"- {yr}: {self._fmt(cash)} 元/股")

        return lines

    # ── Section 2: 管线得分 ──

    def _build_section2_summary(self) -> list[str]:
        lines = ["### 2.1 总体得分", ""]
        lines.append(f"- 最终得分: {self._f.final_score:.1f} / 100")
        lines.append(f"- 归属池: {self._f.pool}")
        lines.append(f"- HardGate: {'PASS' if self._f.hard_gate_passed else 'VETO'}")
        lines.append(f"- 公司分类: {self._f.classify_type}")
        lines.append("")
        lines.append("| 层级 | 得分 | 满分 | 占比 |")
        lines.append("|------|------|------|------|")
        lines.append(f"| L2 (门控) | {self._f.l2_score:.1f} | 20 | 仅展示 |")
        lines.append(f"| L3 (商业模式) | {self._f.l3_score:.1f} | 30 | {self._f.l3_score / 30 * 100:.0f}% |")
        lines.append(f"| L4 (穿透回报率) | {self._f.l4_score:.1f} | 45 | {self._f.l4_score / 45 * 100:.0f}% |")
        lines.append(f"| L5 (安全边际) | {self._f.l5_score:.1f} | 25 | {self._f.l5_score / 25 * 100:.0f}% |")
        lines.append(f"| **Final** | **{self._f.final_score:.1f}** | **100** | **{self._f.final_score:.0f}%** |")
        return lines

    def _build_section2_l3(self) -> list[str]:
        """L3 十二维详情。"""
        lines = ["", f"### 2.2 L3 商业模式 — {self._f.l3_level} ({self._f.l3_score:.1f}/30)", ""]

        dim_scores = self._f.l3_dim_scores or {}
        if not dim_scores:
            lines.append("*(L3 维度数据不可用)*")
            return lines

        lines.append("| 分组 | 维度 | 得分 | 满分 | 说明 |")
        lines.append("|------|------|------|------|------|")
        for dim_id, info in dim_scores.items():
            group = info.get("group", "")
            name = info.get("name", "")
            score = info.get("score", 0)
            label = info.get("label", "")
            lines.append(f"| {group} | {name} | {score:.0f} | 2 | {label} |")

        lines.append(f"| **合计** | | **{self._f.l3_total_dim:.0f}** | **24** | 维度得分 |")
        return lines

    def _build_section2_l4(self) -> list[str]:
        """L4 穿透回报率详情。"""
        lines = ["", f"### 2.3 L4 穿透回报率 ({self._f.l4_score:.1f}/45)", ""]
        lines.append(f"- PR (穿透回报率): {self._f.pr_pct:.2f}%")
        lines.append(f"- 可支配现金: {self._f.pr_disposable_cash / 1e4:.1f} 亿元" if self._f.pr_disposable_cash else "- 可支配现金: N/A")
        lines.append(f"- 分配比率: {self._f.pr_distribution_ratio:.1f}%")
        lines.append(f"- 分配比率来源: {self._f.pr_distribution_source}")
        lines.append(f"- 回购注销: {self._f.pr_buyback_cancellation / 1e4:.1f} 亿元" if self._f.pr_buyback_cancellation else "- 回购注销: 0")
        lines.append(f"- OE 质量标签: {self._f.oe_quality}")
        if self._f.oe_quality != "🟢 可信":
            # v0.33: 展开四项质检明细
            o2p = self._f.oe_to_profit_ratio
            cv = self._f.oe_cv
            cagr = self._f.oe_cagr
            bs_diff = self._f.bs_unexplained_diff_pct
            lines.append(f"  - OE_cf/净利润: {o2p:.2f} ({'≥0.8 ✓' if o2p >= 0.8 else ('≥0.5 ⚠存疑' if o2p >= 0.5 else '<0.5 ✗不可靠')})")
            lines.append(f"  - OE 稳定性 CV: {cv:.2f} ({'≤0.3 ✓' if cv <= 0.3 else ('≤0.5 ⚠偏高' if cv <= 0.5 else '>0.5 ✗不可靠')})")
            lines.append(f"  - OE 趋势 3yr CAGR: {cagr*100:.1f}% ({'✓ 增长' if cagr >= 0 else '⚠ 下滑'})")
            lines.append(f"  - BS 一致性: {bs_diff:.1f}% ({'✓ 正常' if bs_diff <= 30 else '⚠ 差异大'})")
            start = self._f.pr_starting_score
            penalty = self._f.pr_quality_penalty
            if "存疑" in self._f.oe_quality:
                discount = start * 0.3
                l4_internal = max(0, start - penalty - discount)
                lines.append(f"  - 扣分: 起点{start:.0f} - 质检{penalty:.0f} - 存疑×0.30({discount:.1f}) = {l4_internal:.1f} → 缩放{self._f.l4_score:.1f}")
            else:
                lines.append(f"  - 扣分: 起点{start:.0f} - 质检{penalty:.0f} = L4 {self._f.l4_score:.1f}")
        # v0.33 fix: oe_cf_median 原始单位是元，/1e8 才是亿元
        lines.append(f"- OE_cf 中位数: {self._f.oe_cf_median / 1e8:.1f} 亿元" if self._f.oe_cf_median else "- OE_cf 中位数: N/A")
        lines.append("")
        lines.append("**PR 公式展开**:")
        lines.append(f"PR = (可支配现金 × 分配比率 + 回购注销) / 当前市值")
        lines.append(f"   = ({self._f.pr_disposable_cash / 1e4:.1f}亿 × {self._f.pr_distribution_ratio:.1f}% + {self._f.pr_buyback_cancellation / 1e4:.1f}亿) / 市值")
        return lines

    def _build_section2_l5(self) -> list[str]:
        """L5 安全边际详情。"""
        lines = ["", f"### 2.4 L5 安全边际 ({self._f.l5_score:.1f}/25)", ""]
        lines.append(f"- 安全边际率: {self._f.l5_safety_margin_pct:.1f}%")
        lines.append(f"- 合理市值: {self._f.l5_reasonable_mv / 1e4:.1f} 亿元" if self._f.l5_reasonable_mv else "- 合理市值: N/A")
        lines.append(f"- 估值安全得分: {self._f.l5_valuation_score:.1f} / 15")
        lines.append(f"- 下行缓冲得分: {self._f.l5_downside_score:.1f} / 5")
        lines.append(f"- 仓位得分: {self._f.l5_position_score:.1f} / 5")
        lines.append(f"- 仓位上限: {self._f.position_pct:.1f}%")
        if self._f.l5_downside_details:
            lines.append("")
            lines.append("**下行缓冲明细**:")
            for d in self._f.l5_downside_details:
                name = d.get("name", "")
                score = d.get("score", 0)
                label = d.get("label", "")
                lines.append(f"  - {name}: {score:.1f} ({label})")
        return lines

    # ── Section 3: 财报深度分析 ──

    def _build_section3_financial_insights(self) -> list[str]:
        """财报深度分析洞察。"""
        lines: list[str] = []

        if self._fi is None:
            lines.append("## 三、财报深度分析洞察")
            lines.append("")
            lines.append("*(财报深度分析未执行，无数据)*")
            lines.append("")
            return lines

        # 使用 FinancialInsights 的 markdown 渲染
        from src.calculator.financial_deep_analysis import insights_to_markdown
        md = insights_to_markdown(self._fi)
        lines.append(md)
        return lines

    # ── Section 4: 分析报告撰写指引 (v0.27 重写) ──

    def _build_section4_analysis_guidance(self) -> list[str]:
        """分析报告撰写指引 — 告诉分析 Agent 如何利用以上数据。"""
        lines = [
            "## 四、分析报告撰写指引",
            "",
            "以上三部分为你提供了完整的分析素材：",
            "",
            "1. **Tushare 原始数据** (第一部分) — 三大报表关键行、财务指标趋势、估值快照、分红历史",
            "2. **管线计算得分** (第二部分) — L2门控、L3十二维商业模式评估、L4穿透回报率、L5安全边际",
            "3. **财报深度分析洞察** (第三部分) — 7模块 Python 确定性计算的结构化洞察（收入利润趋势、利润率拆解、ROE杜邦、现金流质量、资产负债健康度、分红政策、营运效率）",
            "",
            "请基于以上数据，结合第五部分的商业知识，撰写个性化投资分析报告：",
            "",
            "- 使用三段式证据链：【数据】→【比较】→【结论】",
            "- 每个结论必须有数据支撑，标注置信度",
            "- 优先采信 Tushare 原始数据和财报深度分析定量结果",
            "- 第五部分的商业知识作为行业背景和上下文参考",
            "- 如数据之间存在矛盾，明确标注并给出你的判断",
            "- 禁止给出买入/卖出/持有的投资建议",
            "",
        ]
        return lines

    # ── Section 5: LLM 商业知识检索 (v0.27 新增) ──

    def _build_section5_business_knowledge(self) -> list[str]:
        """LLM 商业知识检索结果。"""
        lines: list[str] = []

        if self._bk is None:
            lines.append("## 五、LLM 商业知识检索")
            lines.append("")
            lines.append("*(商业知识检索未执行)*")
            lines.append("")
            return lines

        # 使用 BusinessKnowledgeResult 的 to_markdown() 方法
        try:
            md = self._bk.to_markdown()
            lines.append(md)
        except AttributeError:
            # 兼容旧格式（dict 或 None）
            lines.append("## 五、LLM 商业知识检索")
            lines.append("")
            lines.append("*(商业知识格式不兼容)*")
            lines.append("")

        return lines

    # ── Helpers ──

    @staticmethod
    def _to_yi(val: Any, source_unit: str = "yuan") -> str:
        """转为亿元显示。"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "-"
        try:
            v = float(val)
            if source_unit == "wan":
                v = v / 1e4  # 万元 → 亿元
            else:
                v = v / 1e8  # 元 → 亿元
            if abs(v) >= 100:
                return f"{v:.0f}"
            elif abs(v) >= 1:
                return f"{v:.1f}"
            else:
                return f"{v:.2f}"
        except (ValueError, TypeError):
            return str(val)

    @staticmethod
    def _fmt(val: Any) -> str:
        """格式化数值。"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "-"
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return str(val)


# ══════════════════════════════════════════════════════════════
# 快捷函数
# ══════════════════════════════════════════════════════════════


def build_brief_md(
    bundle: StockDataBundle,
    final_score: FinalScore,
    financial_insights: Any = None,
    business_knowledge: Any = None,
) -> str:
    """快捷组装 brief.md。

    Args:
        bundle: Tushare 数据载体
        final_score: 打分结果
        financial_insights: 财报深度分析结果 (FinancialInsights | None)
        business_knowledge: 商业知识检索结果 (BusinessKnowledgeResult | None)

    Returns:
        brief.md 的 Markdown 文本
    """
    builder = BriefMDBuilder(bundle, final_score, financial_insights, business_knowledge)
    return builder.build()
