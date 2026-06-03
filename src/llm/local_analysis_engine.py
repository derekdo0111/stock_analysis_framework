"""
本地分析引擎 — 无 LLM 时的 Python 规则引擎。

基于 Python 量化打分的全部中间结果，对 9 个模块逐一评分并生成三段式证据链。
输出格式与 AnalysisAgent 完全一致（AnalysisResult），无需 LLM 即可产出可读分析。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.calculator.turtle_strategy.scoring import FinalScore
from src.llm.analysis_agent import AnalysisResult


# ── 三段式证据链模板 ─────────────────────────────────────

def _evidence(data: str, compare: str, conclusion: str) -> str:
    """生成标准三段式证据链。"""
    return f"【数据】{data}\n【比较】{compare}\n【结论】{conclusion}"


def _score(val: float, thresholds: list[tuple[float, float, int]]) -> tuple[int, str]:
    """根据阈值返回 (score, 标签)。thresholds = [(min, max, score), ...]"""
    for low, high, s in thresholds:
        if low is not None and high is not None:
            if low <= val <= high:
                return s, ""
        elif low is not None:
            if val >= low:
                return s, ""
        elif high is not None:
            if val <= high:
                return s, ""
    return 3, ""


# ══════════════════════════════════════════════════════════════
# 9 模块分析
# ══════════════════════════════════════════════════════════════

def _analyze_moat(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """护城河深度 — ROE稳定性 + 毛利率稳定性 + L3商业模式等级"""
    roe_stab = fs.l5_extrapolation_dims.get("roe_stability", 2)
    margin_stab = fs.l5_extrapolation_dims.get("margin_stability", 2)
    l3_level = fs.l3_level  # v0.23: 优/良/中/差
    oe_quality = fs.oe_quality

    # 综合评分
    dim_score = (roe_stab + margin_stab) / 2
    if l3_level == "优" and oe_quality.startswith("🟢"):
        score = 5
    elif l3_level in ("优", "良") and dim_score >= 3:
        score = 4
    elif l3_level in ("优", "良", "中"):
        score = 3
    elif dim_score >= 2:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"ROE稳定性: {roe_stab}/5, 毛利率稳定性: {margin_stab}/5, L3商业模式乘数: ×{l3:.1f}, OE质量: {oe_quality}",
        f"得分超过行业平均的商业公司通常在ROE和毛利率上表现出低波动，护城河来自品牌和规模效应",
        f"公司护城河{'较强' if score >= 4 else '一般' if score >= 3 else '偏弱'}，L3乘数{l3:.1f}反映商业模式{'优秀' if l3 >= 1.2 else '良好' if l3 >= 1.0 else '中等'}的持续竞争优势"
    )

    uncertainty = "品牌护城河的量化评估受限于市场份额数据的可得性" if score >= 3 else "护城河指标偏低，建议关注行业竞争格局变化"
    return {"score": score, "confidence": "high" if dim_score >= 3 else "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_management(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """管理层质量 — 审计结果 + 审计师更换 + L5管理层稳定性 + PR质量"""
    audit_pass = fs.hard_gate_passed
    mgmt_stab = fs.l5_extrapolation_dims.get("management_stability", 3)
    pr_pct = fs.pr_pct
    oe_quality = fs.oe_quality

    # 分红慷慨度和管理层稳定性
    if audit_pass and mgmt_stab >= 4 and pr_pct >= 8:
        score = 5
    elif audit_pass and mgmt_stab >= 3 and pr_pct >= 5:
        score = 4
    elif audit_pass and oe_quality.startswith("🟢"):
        score = 3
    elif audit_pass:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"HardGate审计: {'PASS' if audit_pass else 'FAIL'}, 管理层稳定性: {mgmt_stab}/5, PR: {pr_pct:.2f}%, OE: {oe_quality}",
        f"审计意见{'' if audit_pass else '不'}标准、{'管理层稳定' if mgmt_stab >= 3 else '管理层数据有限'}、穿透回报率{pr_pct:.2f}%{'高于' if pr_pct >= 5 else '低于'}5%门槛",
        f"管理层{'可信度较高' if score >= 4 else '中规中矩' if score >= 3 else '存在一些不确定性'}，{'分红记录表明与股东利益一致' if pr_pct >= 5 else '穿透回报率偏低需关注资本配置意愿'}"
    )

    uncertainty = "管理层评估受限于公开数据，无法考察诚信度等软性指标" if score >= 3 else "审计和管理层指标偏低，建议深入了解"
    return {"score": score, "confidence": "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_industry(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """行业格局 — 分类 + 行业可预测性 + L3商业模式等级"""
    cls = fs.classify_type
    industry_pred = fs.l5_extrapolation_dims.get("industry_predictability", 3)
    l3_level = fs.l3_level  # v0.23: 优/良/中/差

    if cls == "STANDARD_CONSUMER" and l3_level == "优":
        score = 5
    elif cls == "STANDARD_CONSUMER" and industry_pred >= 3:
        score = 4
    elif cls == "STANDARD_CONSUMER":
        score = 3
    elif industry_pred >= 2:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"公司分类: {cls}, 行业可预测性: {industry_pred}/5, L3: ×{l3:.1f}",
        f"{'标准消费品' if cls == 'STANDARD_CONSUMER' else cls}类公司通常{'有' if l3 >= 1.0 else '缺乏'}稳定的行业竞争格局，行业可预测性{'高' if industry_pred >= 3 else '低'}",
        f"行业格局{'稳固，公司在行业中处于有利位置' if score >= 4 else '一般，存在竞争不确定性' if score >= 3 else '面临挑战'}"
    )

    uncertainty = "行业格局分析基于静态数据，未考虑技术颠覆风险" if score >= 3 else "行业指标偏差，建议关注行业趋势变化"
    return {"score": score, "confidence": "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_growth(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """成长质量 — 营收稳定性 + OE增长趋势 + CAPEX系数"""
    rev_stab = fs.l5_extrapolation_dims.get("revenue_stability", 2)
    oe_cagr = fs.oe_cagr
    capex_coef = fs.capex_coefficient

    # 营收稳定 + OE正增长 + 低CAPEX = 高质量增长
    if rev_stab >= 4 and oe_cagr > 0.05 and capex_coef < 0.5:
        score = 5
    elif rev_stab >= 3 and oe_cagr > 0:
        score = 4
    elif rev_stab >= 2:
        score = 3
    elif oe_cagr > -0.05:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"营收稳定性: {rev_stab}/5, OE 3年CAGR: {oe_cagr * 100:.1f}%, 维持性CAPEX系数: {capex_coef:.2f}",
        f"营收{'稳定' if rev_stab >= 3 else '波动'}、OE{'正增长' if oe_cagr > 0 else '负增长' if oe_cagr < 0 else '持平'}、维持性CAPEX{'低' if capex_coef < 0.5 else '高'}表明{'内生性增长强劲' if score >= 4 else '增长质量需关注'}",
        f"成长质量{'优秀，以内生性驱动为主' if score >= 4 else '良好' if score >= 3 else '一般，增长可能依赖外部投入'}"
    )

    uncertainty = "营收增长的质量评估需要结合量价拆分，目前仅有总量数据" if score >= 3 else "OE负增长可能是周期性的，但建议验证增长可持续性"
    return {"score": score, "confidence": "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_financial_health(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """财务健康度 — L2财务质量 + 价值陷阱负债 + L5安全边际"""
    fin_quality = fs.l2_details.get("financial_quality", 3)
    debt_triggered = "负债压力" in fs.l5_traps_triggered
    trap_level = fs.l5_trap_level
    oe_quality = fs.oe_quality

    if fin_quality >= 8 and not debt_triggered and oe_quality.startswith("🟢"):
        score = 5
    elif fin_quality >= 6 and not debt_triggered:
        score = 4
    elif fin_quality >= 4 and trap_level in ("低风险", "中风险"):
        score = 3
    elif not debt_triggered:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"L2财务质量: {fin_quality}/9, 负债压力触发: {'是' if debt_triggered else '否'}, 陷阱等级: {trap_level}, OE: {oe_quality}",
        f"财务质量得分{fin_quality}、{'存在' if debt_triggered else '无'}负债压力信号、整体风险{'' if trap_level == '低风险' else '偏高'}",
        f"财务健康度{'优秀' if score >= 4 else '良好' if score >= 3 else '一般'}，{'偿债能力强，财务弹性充足' if score >= 4 else '建议关注负债结构和现金流匹配'}"
    )

    uncertainty = "财务健康度基于静态指标，未考虑或有负债和表外事项" if score >= 3 else "负债压力信号需进一步调查具体负债结构和偿债计划"
    return {"score": score, "confidence": "high" if fin_quality >= 6 else "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_capital_allocation(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """资本配置能力 — PR + OE质量 + L4得分"""
    pr_pct = fs.pr_pct
    pr_start = fs.pr_starting_score
    l4 = fs.l4_score
    oe_quality = fs.oe_quality
    pr_years = fs.pr_year_details

    # PR高且稳定 = 资本配置好
    if pr_pct >= 12 and l4 >= 30:
        score = 5
    elif pr_pct >= 8 and l4 >= 15:
        score = 4
    elif pr_pct >= 5 and oe_quality.startswith("🟢"):
        score = 3
    elif pr_pct > 0:
        score = 2
    else:
        score = 1

    years_str = ", ".join(f"{y['year']}:{y['pr_pct']:.1f}%" for y in pr_years[:5]) if pr_years else "N/A"
    evidence = _evidence(
        f"穿透回报率: {pr_pct:.2f}%, L4得分: {l4}/40, OE质量: {oe_quality}, 逐年PR: [{years_str}]",
        f"PR{'高于' if pr_pct >= 8 else '低于'}8%优秀线，{'资本配置得当，股东回报机制良好' if score >= 4 else '资本配置需改善'}",
        f"资本配置能力{'优秀' if score >= 4 else '一般' if score >= 3 else '偏弱'}，{'分红+回购策略为股东创造了可观回报' if pr_pct >= 5 else '股东现金回报偏低，建议关注资本支出的效率'}"
    )

    uncertainty = "资本配置评估基于历史和静态数据，未考虑未来投资计划" if score >= 3 else "PR<5%触发L4=0，资本配置存在显著改善空间"
    return {"score": score, "confidence": "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_accounting(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """会计质量 — 审计意见 + OE/profit比率 + 资产质量陷阱"""
    audit_checks = fs.hard_gate_checks
    audit_ok = any(c.get("name", "").startswith("audit_opinion") for c in audit_checks)
    asset_trap = "资产质量" in fs.l5_traps_triggered
    oe_cv = fs.oe_cv
    oe_quality = fs.oe_quality

    if audit_ok and not asset_trap and oe_quality.startswith("🟢") and oe_cv < 0.2:
        score = 5
    elif audit_ok and not asset_trap and oe_quality.startswith("🟢"):
        score = 4
    elif audit_ok and oe_quality.startswith("🟡"):
        score = 3
    elif asset_trap:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"审计意见: {'标准无保留' if audit_ok else '异常'}, 资产质量陷阱: {'触发' if asset_trap else '无'}, OE变异系数: {oe_cv:.2f}, OE标签: {oe_quality}",
        f"{'审计干净' if audit_ok else '审计异常'}、{'应收/存货增速异常需关注' if asset_trap else '资产质量未触发陷阱'}、OE{'变异系数可控' if oe_cv < 0.3 else '波动偏大'}",
        f"会计质量{'可靠' if score >= 4 else '基本可信但有关注点' if score >= 3 else '存在红旗信号需深入核查'}"
    )

    uncertainty = "会计质量评估基于预警信号，未审计原始凭证" if score >= 3 else "资产质量陷阱和审计异常信号叠加，建议查阅年报附注中的应收账款账龄和存货明细"
    return {"score": score, "confidence": "medium",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_governance(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """公司治理 — 治理风险陷阱 + 审计师更换"""
    governance_trap = "治理风险" if any("治理" in t for t in fs.l5_traps_triggered) else ""
    auditor_changes = 0
    for c in fs.hard_gate_checks:
        if "auditor" in c.get("name", ""):
            val = c.get("value", "0")
            try:
                auditor_changes = int(val)
            except (ValueError, TypeError):
                pass

    if not governance_trap and auditor_changes == 0:
        score = 4
    elif not governance_trap and auditor_changes <= 1:
        score = 3
    elif governance_trap:
        score = 2
    else:
        score = 1

    evidence = _evidence(
        f"治理风险陷阱: {'触发' if governance_trap else '无'}, 审计师更换: {auditor_changes}次/3年",
        f"治理风险{'已触发' if governance_trap else '未触发'}、审计师{'稳定' if auditor_changes == 0 else '有更换'}",
        f"公司治理{'良好，未发现明显问题' if score >= 4 else '存在一些关注点' if score >= 3 else '存在隐患需深入了解'}"
    )

    uncertainty = "公司治理评估受限于公开数据，无法全面评估董事会独立性和关联交易" if score >= 3 else "治理指标偏差，建议审查大股东质押和关联交易"
    return {"score": score, "confidence": "low",
            "evidence": evidence, "uncertainty": uncertainty}


def _analyze_risk(fs: FinalScore, _profile: dict) -> dict[str, Any]:
    """风险因子（反向计分）— L5陷阱 + 仓位 + 外推可行度"""
    trap_count = len(fs.l5_traps_triggered)
    trap_level = fs.l5_trap_level
    extrapolation_level = fs.l5_extrapolation_level
    position_pct = fs.position_pct

    if trap_count == 0 and extrapolation_level == "高可行":
        score = 5
    elif trap_count <= 1 and extrapolation_level in ("高可行", "中可行"):
        score = 4
    elif trap_count <= 2:
        score = 3
    elif trap_count <= 3:
        score = 2
    else:
        score = 1

    traps_str = ", ".join(fs.l5_traps_triggered) if fs.l5_traps_triggered else "无"
    evidence = _evidence(
        f"价值陷阱触发: {trap_count}项 [{traps_str}], 外推可行度: {extrapolation_level}, 建议仓位: {position_pct}%",
        f"触发{trap_count}项陷阱、外推可行度{extrapolation_level}，{'风险敞口较小' if score >= 4 else '存在一定风险'}",
        f"整体风险{'可控' if score >= 4 else '中等，需要持续关注' if score >= 3 else '偏高，建议分散配置'}，{'仓位已受限' if position_pct <= 2 else '仓位尚可'}于{position_pct}%"
    )

    uncertainty = "风险评估基于历史数据，不预测黑天鹅事件" if score >= 3 else "多项陷阱叠加，建议逐一排查具体风险来源"
    return {"score": score, "confidence": "medium" if trap_count <= 2 else "low",
            "evidence": evidence, "uncertainty": uncertainty}


# ══════════════════════════════════════════════════════════════
# 主引擎
# ══════════════════════════════════════════════════════════════

_MODULES = [
    ("moat",            "护城河深度",     _analyze_moat),
    ("management",      "管理层质量",     _analyze_management),
    ("industry_structure", "行业格局",    _analyze_industry),
    ("growth_quality",  "成长质量",       _analyze_growth),
    ("financial_health","财务健康度",     _analyze_financial_health),
    ("capital_allocation","资本配置能力", _analyze_capital_allocation),
    ("accounting_quality","会计质量",     _analyze_accounting),
    ("governance",      "公司治理",       _analyze_governance),
    ("risk_factors",    "风险因子",       _analyze_risk),
]


def run_local_analysis(fs: FinalScore, profile: dict[str, Any] | None = None) -> AnalysisResult:
    """使用 Python 规则引擎对 9 个模块逐一打分，生成三段式证据链。

    Args:
        fs: 阶段二乘法打分结果（含全部中间数据）
        profile: 额外数据（预留，暂未使用）

    Returns:
        AnalysisResult — 与 LLM 输出格式完全一致
    """
    profile = profile or {}

    result = AnalysisResult(ts_code=fs.ts_code, name=fs.name, success=True)
    result.error = ""
    module_details = []
    module_scores: dict[str, float] = {}
    red_flags: list[str] = []

    for mod_id, mod_name, analyzer in _MODULES:
        try:
            mod_result = analyzer(fs, profile)
        except Exception:
            mod_result = {"score": 2, "confidence": "low",
                          "evidence": f"【数据】数据不足【比较】无法与历史/行业对比【结论】无法做出可靠判断",
                          "uncertainty": "该模块数据不完整或计算异常"}

        score = int(mod_result["score"])
        module_scores[mod_name] = score
        module_details.append({
            "module": mod_name,
            "score": score,
            "confidence": mod_result.get("confidence", "medium"),
            "evidence": mod_result.get("evidence", ""),
            "uncertainty": mod_result.get("uncertainty", ""),
        })

        # 自动收集红旗
        if score <= 1:
            red_flags.append(f"[{mod_name}] 评分{score}/5，建议重点关注")

    result.qualitative_total = float(sum(module_scores.values()))
    result.module_scores = module_scores
    result.module_details = module_details
    result.red_flags = red_flags

    # 商业模式判断 (v0.23: 使用 L3 十二维评分替代旧乘数)
    avg = result.qualitative_total / 9
    l3_level = fs.l3_level or "中"  # v0.23: 优/良/中/差
    l3_score = fs.l3_score
    l3_dim = fs.l3_total_dim
    if avg >= 4.0 and l3_level == "优":
        result.business_model = "优"
        result.business_model_reasoning = f"9模块均分{avg:.1f}/5，L3十二维{l3_dim:.0f}/24({l3_score:.1f}/30)，商业模式优秀"
    elif avg >= 3.0:
        result.business_model = "良"
        result.business_model_reasoning = f"9模块均分{avg:.1f}/5，L3十二维{l3_dim:.0f}/24({l3_score:.1f}/30)，商业模式良好"
    elif avg >= 2.0:
        result.business_model = "中"
        result.business_model_reasoning = f"9模块均分{avg:.1f}/5，L3十二维{l3_dim:.0f}/24({l3_score:.1f}/30)，商业模式一般"
    else:
        result.business_model = "差"
        result.business_model_reasoning = f"9模块均分{avg:.1f}/5，多项指标偏低，商业模式存疑"

    return result
