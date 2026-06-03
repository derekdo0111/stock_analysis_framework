"""
LLM 交叉验证 Agent v0.27 — 事实核查模式。

v0.27 重构:
- 输入从 brief.md 改为 (分析报告 + brief.md源数据)
- 验证靶子从「管线得分」改为「分析Agent的分析结论」
- System prompt 改为事实核查员角色
- 移除任务一（商业知识检索），商业知识已是 brief.md 的输入
- 使用 LLM_VALIDATION_MODEL 独立模型配置

输出: 逐条结论标注 ✓源数据可支撑 / ⚠过度解读 / ✗与源数据矛盾 / ?缺乏证据

用法:
    from src.llm.cross_validation_agent import CrossValidationAgent
    agent = CrossValidationAgent()
    result = agent.validate(analysis_result, brief_md, company_name, ts_code)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.llm.client import LLMClient, LLMConfig


# ══════════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════════


@dataclass
class Discrepancy:
    """单条事实核查记录。"""
    dimension: str           # 被核查的维度/声明
    quantitative_score: str   # 分析报告中给出的评分/判断
    evidence: str             # brief.md 中的源数据证据
    judgment: str             # "✓源数据可支撑" / "⚠过度解读" / "✗与源数据矛盾" / "?缺乏证据"
    suggestion: str           # 修正建议
    severity: str = "INFO"   # INFO / WARNING / CRITICAL


@dataclass
class CrossValidationResult:
    """交叉验证结果。"""

    ts_code: str
    name: str = ""

    # 逐条不一致记录
    discrepancies: list[Discrepancy] = field(default_factory=list)

    # 汇总
    total_checked: int = 0
    supported_count: int = 0      # ✓源数据可支撑
    overstatement_count: int = 0  # ⚠过度解读
    conflict_count: int = 0       # ✗与源数据矛盾
    evidence_lack_count: int = 0  # ?缺乏证据

    # 总结
    overall_verdict: str = ""
    key_findings: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

    # 状态
    success: bool = False
    error: str = ""
    used_fallback: bool = False


# ══════════════════════════════════════════════════════════════
# v0.27 System Prompt — 事实核查员
# ══════════════════════════════════════════════════════════════

_CV_SYSTEM_PROMPT_V27 = """你是一位独立的事实核查员（Fact Checker）。你的工作是：

## 任务
逐条检查《分析报告》中的每个关键判断和结论，验证它们是否在《数据底稿》(brief.md) 中有充分的源数据支撑。

## 核查维度
请重点关注以下方面：
1. **数值引用准确性**: 报告中的数字是否与 brief.md 完全一致
2. **趋势判断**: 报告中的"增长/下降/改善/恶化"等趋势判断是否符合数据
3. **因果推断**: 报告中的归因是否有数据支撑（如"因ROE下降导致..."）
4. **行业/管理层断言**: 报告中关于行业地位、管理层质量的判断是否与 brief.md Section 5 商业知识一致
5. **红旗遗漏**: brief.md 中存在的重大风险信号是否被报告忽略

## 标注标准

对每条声明标注以下四种结论之一：

- **✓源数据可支撑**: 声明有充分的数据支持，数值引用正确
- **⚠过度解读**: 数据部分支持声明，但报告做了过度的推断或夸大
- **✗与源数据矛盾**: 声明与 brief.md 中的数据直接矛盾
- **?缺乏证据**: 声明在 brief.md 中找不到任何支撑证据

## 输出格式（严格 JSON）
{
  "discrepancies": [
    {
      "dimension": "被检查的声明/维度",
      "quantitative_score": "分析报告中的原话或评分",
      "evidence": "brief.md 中的源数据证据（引用具体数字）",
      "judgment": "✓源数据可支撑|⚠过度解读|✗与源数据矛盾|?缺乏证据",
      "suggestion": "修正建议（如无问题则写'无'）",
      "severity": "INFO|WARNING|CRITICAL"
    }
  ],
  "overall_verdict": "总体核查结论（2-3句话）",
  "key_findings": ["最关键的事实核查发现1", "发现2"],
  "red_flags": ["需要立即关注的红旗"]
}

## 规则
- 每条 discrepancy 必须引用 brief.md 中的具体数据作为 evidence
- 不要在 evidence 中编造 brief.md 不存在的数字
- 如果分析报告整体合理且数据支撑充分，discrepancies 可以为空数组
- severity 分级: INFO=细微偏差, WARNING=中等问题, CRITICAL=严重错误或红旗遗漏
- 使用中文输出"""


# ══════════════════════════════════════════════════════════════
# 降级规则引擎（无 LLM 时使用）
# ══════════════════════════════════════════════════════════════


def _fallback_validate(
    analysis_text: str,
    brief_md: str,
    company_name: str = "",
    ts_code: str = "",
) -> CrossValidationResult:
    """降级规则引擎 — 分析报告 vs brief.md 简单关键词对比。"""
    result = CrossValidationResult(
        ts_code=ts_code,
        name=company_name,
        success=True,
        used_fallback=True,
    )

    discrepancies: list[Discrepancy] = []

    # 检查 brief.md 是否包含必要数据
    has_financial_insights = "## 三、财报深度分析洞察" in brief_md
    has_business_knowledge = "## 五、LLM 商业知识检索" in brief_md

    if not has_financial_insights:
        discrepancies.append(Discrepancy(
            dimension="数据完整性",
            quantitative_score="—",
            evidence="brief.md 缺少「三、财报深度分析洞察」",
            judgment="?缺乏证据",
            suggestion="财报深度分析未执行，无法验证分析报告中的财务趋势判断",
            severity="WARNING",
        ))

    if not has_business_knowledge:
        discrepancies.append(Discrepancy(
            dimension="数据完整性",
            quantitative_score="—",
            evidence="brief.md 缺少「五、LLM 商业知识检索」",
            judgment="?缺乏证据",
            suggestion="商业知识检索未执行，无法验证分析报告中的商业判断",
            severity="INFO",
        ))

    # 简单关键词扫描：检测常见红旗模式
    checks = [
        ("ROE下降但评分高", "ROE.*下降", "ROE.*得分.*高"),
        ("现金流质量差但未警示", "现金流质量=差劲", ""),
        ("负债率高但未警示", "负债率.*>.*70", ""),
        ("分红不连续但评分高", "分红.*中断", ""),
    ]

    for desc, pos_pattern, _ in checks:
        import re
        if re.search(pos_pattern, brief_md):
            discrepancies.append(Discrepancy(
                dimension=f"潜在问题 - {desc}",
                quantitative_score="需 LLM 核查",
                evidence=f"brief.md 检测到模式: {pos_pattern}",
                judgment="⚠过度解读",
                suggestion=f"可能与分析报告冲突，需 LLM 进一步核查",
                severity="WARNING",
            ))

    result.discrepancies = discrepancies
    result.total_checked = len(checks) + 2
    result.supported_count = 0
    result.overstatement_count = len([d for d in discrepancies if d.judgment == "⚠过度解读"])
    result.conflict_count = 0
    result.evidence_lack_count = len([d for d in discrepancies if d.judgment == "?缺乏证据"])
    result.overall_verdict = (
        f"降级规则引擎: 扫描 {len(checks)} 个维度，"
        f"发现 {len(discrepancies)} 个需注意的项"
    )
    result.key_findings = [
        "⚠️ 当前使用降级规则引擎，仅做简单关键词扫描",
        "建议配置 DEEPSEEK_API_KEY 以获得完整的 LLM 事实核查",
    ]

    return result


# ══════════════════════════════════════════════════════════════
# 交叉验证 Agent
# ══════════════════════════════════════════════════════════════


class CrossValidationAgent:
    """LLM 交叉验证 Agent (v0.27 重构 — 事实核查模式)。

    读取分析报告 + brief.md（源数据），逐条核查分析结论是否与源数据一致。

    降级：无 API Key → Python 规则引擎。
    """

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient(model=LLMConfig.validation_model())
        self._client = client

    def validate(
        self,
        analysis_text: str,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> CrossValidationResult:
        """执行事实核查 — 验证分析报告结论 vs 数据底稿。

        Args:
            analysis_text: Phase 5a 分析 Agent 产出的完整分析报告（或 JSON 字符串）
            brief_md: 数据底稿全文（5个Section，作为事实核查的源数据）
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            CrossValidationResult 含逐条核查记录
        """
        if self._client is None:
            logger.info("LLM 不可用，使用降级规则引擎")
            return _fallback_validate(analysis_text, brief_md, company_name, ts_code)

        # 截断过长的文本（保留源数据完整性优于分析报告）
        max_brief = 12000
        max_analysis = 4000
        brief = brief_md[:max_brief] + ("\n\n...(内容已截断)" if len(brief_md) > max_brief else "")
        analysis = analysis_text[:max_analysis] + ("\n\n...(内容已截断)" if len(analysis_text) > max_analysis else "")

        user_prompt = f"""## 待核查的分析报告

{analysis}

---

## 数据底稿（源数据，以此为准）

{brief}

---

请逐条核查分析报告中的关键判断，标注 ✓/⚠/✗/? 并输出 JSON。"""

        try:
            response = self._client.chat(
                system_prompt=_CV_SYSTEM_PROMPT_V27,
                user_message=user_prompt,
                temperature=0.0,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")
            return _fallback_validate(analysis_text, brief_md, company_name, ts_code)

        return self._parse_response(response, company_name, ts_code)

    def _parse_response(
        self,
        response_text: str,
        company_name: str,
        ts_code: str,
    ) -> CrossValidationResult:
        """解析 LLM JSON 响应。"""
        import json as _json

        result = CrossValidationResult(
            ts_code=ts_code,
            name=company_name,
            success=False,
        )

        try:
            text = response_text.strip()
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()

            data = _json.loads(text)
        except (_json.JSONDecodeError, ValueError) as e:
            logger.warning(f"LLM JSON 解析失败: {e}")
            result.error = f"JSON 解析失败: {e}"
            return result

        # ── 解析 discrepancies ──
        disc_list = data.get("discrepancies", [])
        for d in disc_list:
            result.discrepancies.append(Discrepancy(
                dimension=d.get("dimension", ""),
                quantitative_score=d.get("quantitative_score", ""),
                evidence=d.get("evidence", ""),
                judgment=d.get("judgment", "?缺乏证据"),
                suggestion=d.get("suggestion", ""),
                severity=d.get("severity", "INFO"),
            ))

        # ── 统计 ──
        result.total_checked = len(result.discrepancies)
        result.supported_count = sum(
            1 for d in result.discrepancies if d.judgment.startswith("✓")
        )
        result.overstatement_count = sum(
            1 for d in result.discrepancies if d.judgment.startswith("⚠")
        )
        result.conflict_count = sum(
            1 for d in result.discrepancies if d.judgment.startswith("✗")
        )
        result.evidence_lack_count = sum(
            1 for d in result.discrepancies if d.judgment.startswith("?")
        )

        # ── 总结 ──
        result.overall_verdict = data.get("overall_verdict", "")
        result.key_findings = data.get("key_findings", [])
        result.red_flags = data.get("red_flags", [])

        result.success = True
        return result
