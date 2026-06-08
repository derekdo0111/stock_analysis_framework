"""
LLM 交叉验证 Agent v0.30 — 结构化声明核查模式。

v0.30 重构:
- 加载 cv_methodology_brief.md 注入 System Prompt（项目公式+打分逻辑背景）
- 新增 verify_claim() 方法: 按 claim_type 分策略逐条核查
- 保留 validate() 向后兼容（全文核查，v0.27 模式）

v0.27 重构:
- 输入从 brief.md 改为 (分析报告 + brief.md源数据)
- 验证靶子从「管线得分」改为「分析Agent的分析结论」
- System prompt 改为事实核查员角色
- 移除任务一（商业知识检索），商业知识已是 brief.md 的输入
- 使用 LLM_VALIDATION_MODEL 独立模型配置

输出: 逐条结论标注 ✓源数据可支撑 / ⚠过度解读 / ✗与源数据矛盾 / ?缺乏证据

用法:
    from src.turtle.llm.cross_validation_agent import CrossValidationAgent
    agent = CrossValidationAgent()
    # v0.30: 逐条核查
    result = agent.verify_claim(claim, brief_context)
    # v0.27: 全文核查（向后兼容）
    result = agent.validate(analysis_result, brief_md, company_name, ts_code)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from src.turtle.llm.claim_types import AnalysisClaim, VerifiedClaim
from src.core.llm.client import LLMClient, LLMConfig


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

# v0.30: 逐条核查专用 System Prompt（含项目方法论文档）
_CV_CLAIM_CHECK_PROMPT = """你是一位独立的事实核查员（Fact Checker）。

## 你的知识背景

你已经阅读了「龟龟投资策略方法论文档」，了解该项目的：
- 评分架构: Final = L3(0-30) + L4(0-45) + L5(0-25) = 100pt
- L4 穿透回报率公式: PR = (可支配现金 × 分配比率 + 回购注销) / 当前市值
- L5 安全边际公式: 合理市值 = (DC × 分配比率 + 回购注销) / 7%
- OE 质量标签: 🟢可信 / 🟡存疑 / 🔴不可靠
- L3 十二维打分规则（每维 0-2 分）

## 核查策略（按声明类型）

对于每种声明类型，采用不同的核查方法：

### pipeline_calculation (管线计算数值)
→ 用你已知的项目公式，从 brief.md 中取组件值**复算验证**。
→ 不要因为 brief.md 中搜不到中间计算结果而标 ?缺乏证据。
→ 复算结果匹配 → ✓ | 组件缺失 → ? | 结果不一致 → ✗

### data_citation (原始数据引用)
→ 在 brief.md 中直接搜索该数值，完全一致 → ✓。
→ 找不到 → ?缺乏证据 | 数字有出入 → ✗矛盾

### trend_judgment (趋势判断)
→ 查看 brief.md Section 三 财报深度分析洞察是否有对应的趋势分析。
→ 有明确支持 → ✓ | 部分支持 → ⚠ | 矛盾 → ✗

### business_assertion (商业知识断言)
→ 查看 brief.md Section 五 商业知识检索是否有对应信息。
→ 有对应 → ✓ | 找不到 → ?缺乏证据

### qualitative_score (分析 Agent 主观打分)
→ **不核查分数大小是否合理**，只核查：
→ 引用的数据是否准确 | 证据链是否完整 | 有无与 brief.md 矛盾之处
→ 如果数据引用正确且无矛盾 → ✓
→ 如果有数据引用错误 → ✗

## 输出格式（严格 JSON）

对每条声明输出：
{
  "judgment": "✓源数据可支撑|⚠过度解读|✗与源数据矛盾|?缺乏证据",
  "evidence": "brief.md 中的源数据证据（引用具体数字或公式推算过程）",
  "suggestion": "修正建议（如无问题写'无'）",
  "severity": "INFO|WARNING|CRITICAL",
  "cv_confidence": "high|medium|low"
}

## 规则
- evidence 必须引用 brief.md 中的具体数据或你的公式推算步骤
- 不要在 evidence 中编造 brief.md 不存在的数字
- pipeline_calculation 类型的声明，用公式复算，不要盲目搜数字
- qualitative_score 类型的声明，不评判分数的合理性
- 使用中文输出"""


# ── v0.31: 批量核查 prompt（仅核查 trend_judgment / business_assertion / qualitative_score）──

_CV_BATCH_CLAIM_CHECK_PROMPT = """你是一位独立的事实核查员（Fact Checker）。

## 你的知识背景

你已经阅读了「龟龟投资策略方法论文档」，了解该项目的评分架构和公式。

## 任务

你将收到一批**核心主张**（key claims），需要逐条对照数据底稿（brief.md）进行事实核查。
注意：这些声明只包含趋势判断、商业判断和主观打分——管线数值和数据引用已由代码验证，不在此列。

## 核查策略（仅 3 种声明类型）

### trend_judgment (趋势判断)
→ 查看 brief.md Section 三 财报深度分析洞察是否有对应的趋势分析。
→ 有明确支持 → ✓源数据可支撑 | 部分支持 → ⚠过度解读 | 矛盾 → ✗与源数据矛盾

### business_assertion (商业知识断言)
→ 查看 brief.md Section 五 商业知识检索是否有对应信息。
→ 有对应 → ✓ | 找不到 → ?缺乏证据

### qualitative_score (分析 Agent 主观打分)
→ **不核查分数大小是否合理**，只核查：
→ 引用的数据是否准确 | 证据链是否完整 | 有无与 brief.md 矛盾之处
→ 如果数据引用正确且无矛盾 → ✓
→ 如果有数据引用错误 → ✗

## 输出格式（严格 JSON）

一次性输出**全部声明**的核查结果，每条必须包含 claim_id 与原输入对应：
{
  "verifications": [
    {
      "claim_id": "claim_01",
      "judgment": "✓源数据可支撑|⚠过度解读|✗与源数据矛盾|?缺乏证据",
      "evidence": "brief.md 中的源数据证据（引用具体数字）",
      "suggestion": "修正建议（如无问题写'无'）",
      "severity": "INFO|WARNING|CRITICAL",
      "cv_confidence": "high|medium|low"
    }
  ]
}

## 规则
- evidence 必须引用 brief.md 中的具体数据
- 不要在 evidence 中编造 brief.md 不存在的数字
- qualitative_score 类型的声明，不评判分数的合理性
- 使用中文输出
- **每条声明的 claim_id 必须与原输入严格一致**
- **不要遗漏任何一条声明**"""


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
    """LLM 交叉验证 Agent (v0.30 — 结构化声明核查模式)。

    读取分析报告 + brief.md（源数据），逐条核查分析结论是否与源数据一致。

    v0.30: 新增 verify_claim() — 按声明类型分策略核查，注入项目方法论文档。
    v0.27: validate() 保留 — 全文核查模式（向后兼容）。

    降级：无 API Key → Python 规则引擎。
    """

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient(model=LLMConfig.validation_model())
        self._client = client
        self._methodology = self._load_methodology()

    @staticmethod
    def _load_methodology() -> str:
        """加载 CV Agent 专属方法论文档。"""
        # 尝试多个可能的路径
        candidates = [
            Path(__file__).parent.parent / "rules" / "cv_methodology_brief.md",  # src/turtle/rules/
            Path("src/turtle/rules/cv_methodology_brief.md"),
            Path("rules/cv_methodology_brief.md"),  # legacy fallback
        ]
        for p in candidates:
            if p.exists():
                return p.read_text(encoding="utf-8")
        logger.warning("cv_methodology_brief.md not found, CV Agent 将在无项目知识背景下运行")
        return ""

    def _build_claim_check_system_prompt(self) -> str:
        """构建含方法论文档的 System Prompt。"""
        parts = [_CV_CLAIM_CHECK_PROMPT]
        if self._methodology:
            parts.append("\n\n---\n\n## 项目方法论文档（仅供你参考，不是数据源）\n\n")
            parts.append(self._methodology)
        return "\n".join(parts)

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

    # ── v0.30: 逐条声明核查 ──

    def verify_claim(
        self,
        claim: AnalysisClaim,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> VerifiedClaim:
        """v0.30: 对单条原子声明做核查。

        按 claim_type 采用不同核查策略：
        - pipeline_calculation → 公式复算
        - data_citation → 对表 brief.md
        - trend_judgment → 查 Section 三
        - business_assertion → 查 Section 五
        - qualitative_score → 仅核查数据引用

        Args:
            claim: 分析 Agent 提取的原子声明
            brief_md: 完整数据底稿
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            VerifiedClaim
        """
        result = VerifiedClaim(
            claim=claim,
            claim_id=claim.id,
            dimension=claim.dimension,
            claim_text=claim.claim_text,
            claim_type=claim.claim_type,
            judgment="?缺乏证据",
            evidence="",
            suggestion="",
            severity="INFO",
            cv_confidence="low",
        )

        if self._client is None:
            logger.info("LLM 不可用，跳过单条核查")
            result.evidence = "LLM 不可用，无法执行核查"
            return result

        # 截取 brief.md 相关上下文（根据 claim_type 选择偏重）
        brief_context = self._extract_brief_context(brief_md, claim)

        system_prompt = self._build_claim_check_system_prompt()
        user_prompt = f"""## 声明信息

- 类型: {claim.claim_type}
- 维度: {claim.dimension}
- 声明内容: {claim.claim_text}
- 分析 Agent 自评置信度: {claim.confidence}

## 数据底稿相关部分

{brief_context}

---

请根据声明类型采用对应的核查策略，输出 JSON。"""

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.0,
                max_tokens=2048,
            )
            result.judgment = raw.get("judgment", "?缺乏证据")
            result.evidence = raw.get("evidence", "")
            result.suggestion = raw.get("suggestion", "")
            result.severity = raw.get("severity", "INFO")
            result.cv_confidence = raw.get("cv_confidence", "medium")
        except Exception as e:
            logger.warning(f"单条核查失败 (claim={claim.id}): {e}")
            result.evidence = f"核查异常: {e}"
            result.judgment = "?缺乏证据"

        return result

    def verify_claims_batch(
        self,
        claims: list[AnalysisClaim],
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> list[VerifiedClaim]:
        """v0.31: 一次性批量核查所有声明。

        将所有核心声明打包为一次 LLM 调用，大幅减少 API 调用次数和 token 消耗。
        原 v0.30 逐条调用（100 次 API）→ v0.31 一次调用。

        Args:
            claims: 声明列表（仅 trend_judgment / business_assertion / qualitative_score）
            brief_md: 完整数据底稿
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            list[VerifiedClaim]
        """
        if not claims:
            logger.info("声明列表为空，跳过核查")
            return []

        default_result = VerifiedClaim(
            judgment="?缺乏证据", evidence="LLM 不可用",
            suggestion="", severity="INFO", cv_confidence="low",
        )

        if self._client is None:
            logger.warning("LLM 不可用，返回默认核查结果")
            return [
                VerifiedClaim(
                    claim=c, claim_id=c.id, dimension=c.dimension,
                    claim_text=c.claim_text, claim_type=c.claim_type,
                    judgment=default_result.judgment, evidence=default_result.evidence,
                    suggestion=default_result.suggestion, severity=default_result.severity,
                    cv_confidence=default_result.cv_confidence,
                )
                for c in claims
            ]

        # 截断 brief.md
        brief_truncated = brief_md
        max_brief = 15000
        if len(brief_md) > max_brief:
            brief_truncated = brief_md[:max_brief] + "\n\n...(内容已截断)"

        # 构建声明列表文本
        claim_lines = [
            f"[{c.id}] ({c.claim_type}) {c.dimension} | {c.claim_text} | 自评置信度: {c.confidence}"
            for c in claims
        ]
        claims_text = "\n".join(claim_lines)

        system_prompt = _CV_BATCH_CLAIM_CHECK_PROMPT
        if self._methodology:
            system_prompt += (
                "\n\n---\n\n## 项目方法论文档（仅供你参考，不是数据源）\n\n"
                + self._methodology
            )

        user_prompt = f"""## 待核查声明列表（共 {len(claims)} 条）

{claims_text}

---

## 数据底稿（源数据，以此为准）

{brief_truncated}

---

请逐条核查上述全部声明，输出 JSON。"""

        logger.info(f"CV 批量核查: {len(claims)} 条声明 → 1 次 LLM 调用")

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.0,
                max_tokens=32768,
            )

            verifications = raw.get("verifications", [])
            vc_map: dict[str, dict] = {
                v["claim_id"]: v for v in verifications if "claim_id" in v
            }

            verified: list[VerifiedClaim] = []
            for c in claims:
                v = vc_map.get(c.id, {})
                vc = VerifiedClaim(
                    claim=c,
                    claim_id=c.id,
                    dimension=c.dimension,
                    claim_text=c.claim_text,
                    claim_type=c.claim_type,
                    judgment=v.get("judgment", "?缺乏证据"),
                    evidence=v.get("evidence", ""),
                    suggestion=v.get("suggestion", ""),
                    severity=v.get("severity", "INFO"),
                    cv_confidence=v.get("cv_confidence", "medium"),
                )
                verified.append(vc)
                logger.info(f"  {vc.judgment} | {c.id}: {c.claim_text[:60]}...")

            # 统计
            supported = sum(1 for vc in verified if vc.judgment.startswith("✓"))
            overstating = sum(1 for vc in verified if vc.judgment.startswith("⚠"))
            conflicts = sum(1 for vc in verified if vc.judgment.startswith("✗"))
            lacks = sum(1 for vc in verified if vc.judgment.startswith("?"))
            logger.info(
                f"批量核查完成: ✓{supported} ⚠{overstating} ✗{conflicts} ?{lacks} "
                f"(总数 {len(verified)})"
            )
            return verified

        except Exception as e:
            logger.error(f"批量核查失败: {e}")
            return [
                VerifiedClaim(
                    claim=c, claim_id=c.id, dimension=c.dimension,
                    claim_text=c.claim_text, claim_type=c.claim_type,
                    judgment="?缺乏证据", evidence=f"核查异常: {e}",
                    suggestion="", severity="INFO", cv_confidence="low",
                )
                for c in claims
            ]

    @staticmethod
    def _extract_brief_context(brief_md: str, claim: AnalysisClaim) -> str:
        """根据 claim_type 从 brief.md 中提取最相关的上下文段落。

        不同声明类型关注 brief.md 的不同 Section。
        """
        max_chars = 6000

        # 按声明类型选择重点 Section
        section_labels: list[str]
        if claim.claim_type == "pipeline_calculation":
            section_labels = ["## 一、", "## 二、"]
        elif claim.claim_type == "data_citation":
            section_labels = ["## 一、", "## 二、"]
        elif claim.claim_type == "trend_judgment":
            section_labels = ["## 三、"]
        elif claim.claim_type == "business_assertion":
            section_labels = ["## 五、"]
        elif claim.claim_type == "qualitative_score":
            section_labels = ["## 一、", "## 二、", "## 三、"]
        else:
            section_labels = ["## 一、", "## 二、", "## 三、", "## 五、"]

        # 提取相关 sections
        sections: list[str] = []
        for label in section_labels:
            start = brief_md.find(label)
            if start == -1:
                continue
            # 找到下一个 section 的开始
            end = len(brief_md)
            for other in ["## 一、", "## 二、", "## 三、", "## 四、", "## 五、"]:
                pos = brief_md.find(other, start + len(label))
                if pos != -1 and pos < end:
                    end = pos
            sections.append(brief_md[start:end].strip())

        context = "\n\n---\n\n".join(sections)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n\n...(内容已截断)"
        return context
