"""
分析 Agent — CFA 价值投资研究员 v1.3 (v0.30)。

v0.30 新增:
- extract_claims() 方法: 从完整报告提取原子声明（供 CV 逐条核查）
- revise_with_cv_feedback() 方法: 面对 CV 核查结果做回炉修正

v0.29 新增:
- RootCauseItem / RootCauseAnalysisResult 数据类
- diagnose_root_cause() 方法: 对 CV 问题项做根因反思
- 四种根因分类: 企业真实问题 / 数据质量问题 / 评估规则偏差 / 信息不足

v0.27 变更:
- 输入从 FinalScore + profile 改为完整 brief.md（含原始数据+得分+财报洞察+商业知识）
- 使用 LLM_ANALYSIS_MODEL 独立模型配置
- System prompt 增加「利用商业知识作为行业背景」指引

从 agent_constraints.yaml 加载:
- 第一层: 专业身份 (CFA持证人，15年A股经验)
- 第二层: 行为边界 (证据链/概率语言/禁止投资建议)
- 第三层: 9模块 Rubric 打分量表 (0-5分)
- 第四层: Schema 硬约束 (structured output)

核心创新: 三段式证据链
  【数据】具体数值 → 【比较】历史/行业 → 【结论】推断判断
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.turtle.llm.claim_types import (
    AnalysisClaim,
    VerifiedClaim,
    RevisedClaim,
)
from src.core.llm.client import LLMClient, LLMConfig, LLMError
from src.turtle.rules.loader import load_rules


@dataclass
class AnalysisResult:
    """分析 Agent 输出。"""
    ts_code: str
    name: str = ""

    # 9 模块打分
    module_scores: dict[str, float] = field(default_factory=dict)
    qualitative_total: float = 0.0

    # 各模块详情
    module_details: list[dict[str, Any]] = field(default_factory=list)

    # 商业模式判断
    business_model: str = "良"
    business_model_reasoning: str = ""

    # 红旗警告
    red_flags: list[str] = field(default_factory=list)

    # 完整分析报告文本 (v0.27 新增)
    full_report: str = ""

    # v0.32: 逐章LLM点评
    financial_insight_commentary: str = ""
    business_knowledge_synthesis: str = ""
    l3_scoring_commentary: str = ""
    valuation_commentary: str = ""

    # 状态
    success: bool = False
    error: str = ""

    # 原始 LLM 输出 (调试用)
    raw_output: dict[str, Any] = field(default_factory=dict)


@dataclass
class RootCauseItem:
    """v0.29: 单个 CV 问题项的根因诊断结果。"""
    dimension: str               # 被 CV 标注的维度
    cv_judgment: str             # 原始 CV 结论 (⚠/✗/?)
    cv_evidence: str             # CV 引用的源数据证据
    analysis_claim: str          # 分析 Agent 的原声明

    root_cause: str = ""         # "企业真实问题" | "数据质量问题" | "评估规则偏差" | "信息不足"
    reasoning: str = ""          # 诊断推理 (2-3句)
    confidence: str = "medium"   # "high" | "medium" | "low"

    # 如果是数据问题，需要什么数据来修复
    data_fix_suggestion: str = ""

    # 核心: 尽量还原的企业真实情况
    enterprise_insight: str = ""


@dataclass
class RootCauseAnalysisResult:
    """v0.29: 根因分析完整结果。"""
    ts_code: str
    name: str = ""

    items: list[RootCauseItem] = field(default_factory=list)

    # 统计
    enterprise_issues_count: int = 0
    data_quality_issues_count: int = 0
    methodology_issues_count: int = 0
    insufficient_info_count: int = 0

    # 总结性判断
    summary: str = ""

    success: bool = False
    error: str = ""


class AnalysisAgent:
    """CFA 价值投资研究员 — 9模块定性分析。

    v0.27: 输入改为完整 brief.md（含 Tushare原始数据 + 管线得分 +
           财报深度分析洞察 + 商业知识检索结果）。
    """

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient(model=LLMConfig.analysis_model())
        self._client = client
        self._rules = load_rules()
        self._cfg = self._rules.agent_constraints.analysis_agent

    def analyze(
        self,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> AnalysisResult:
        """基于完整 brief.md 撰写个性化投资分析报告。

        Args:
            brief_md: 完整数据底稿（5个Section: Tushare原始数据 + 管线得分 +
                      财报洞察 + 分析指引 + 商业知识检索结果）
            company_name: 公司名称
            ts_code: 股票代码
        """
        result = AnalysisResult(
            ts_code=ts_code,
            name=company_name,
        )

        if self._client is None:
            # LLM 不可用，使用 Python 默认保守打分
            self._apply_default_scoring(result)
            result.full_report = (
                f"## {company_name} ({ts_code}) — 默认保守分析\n\n"
                "*(LLM API 不可用，使用 Python 规则引擎默认打分)*\n\n"
                "各模块均使用默认保守分（2.5/5），仅供参考。"
                "建议配置 DEEPSEEK_API_KEY 以获得完整的 LLM 分析。\n"
            )
            return result

        # 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(brief_md, company_name, ts_code)

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0,
                max_tokens=32768,
            )
            result.raw_output = raw
            result.success = True

            # 解析输出
            scores = raw.get("module_scores", {})
            result.module_scores = {k: float(v) for k, v in scores.items()}
            result.qualitative_total = float(raw.get("qualitative_total", 0))
            result.business_model = str(raw.get("business_model", {}).get("judgment", "良"))
            result.business_model_reasoning = str(raw.get("business_model", {}).get("reasoning", ""))
            result.red_flags = raw.get("red_flags", [])
            result.module_details = raw.get("module_details", [])
            result.full_report = raw.get("full_report", "")
            result.financial_insight_commentary = raw.get("financial_insight_commentary", "")
            result.business_knowledge_synthesis = raw.get("business_knowledge_synthesis", "")
            result.l3_scoring_commentary = raw.get("l3_scoring_commentary", "")
            result.valuation_commentary = raw.get("valuation_commentary", "")

        except (LLMError, Exception) as e:
            logger.error(f"AnalysisAgent failed: {e}")
            result.error = str(e)
            self._apply_default_scoring(result)

        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示词 — 注入四层约束 + v0.27 商业知识指引。"""
        cfg = self._cfg
        parts = []

        # 第一层: 专业身份
        role = cfg.role
        parts.append(f"""## 专业身份
你是 {role.title}，拥有 {role.experience}。
专注行业: {role.industry_focus if role.industry_focus else "消费品、医药、公用事业"}
核心理念: {role.core_belief}""")

        # 第二层: 行为边界
        must = "\n".join([f"- {m.rule}" for m in cfg.behavior.must_do])
        must_not = "\n".join([f"- {m.rule}" for m in cfg.behavior.must_not_do])
        parts.append(f"""## 行为边界
### 必须做到
{ must }

### 禁止行为
{ must_not }""")

        # 第三层: Rubric 量表 (简化版)
        rubric_lines = []
        for mod in cfg.rubric.modules:
            rubric_lines.append(f"### {mod.name} (0-5分)")
            rubric_lines.append(f"{mod.description}")
            for s in mod.scale[:3]:  # 只展示前3个等级节省 token
                rubric_lines.append(f"  {s.score}分: {s.description[:80]}")
        parts.append("## 打分量表\n" + "\n".join(rubric_lines))

        # v0.27: 商业知识指引
        parts.append("""## 商业知识使用指引
数据底稿中「五、LLM 商业知识检索」部分已经包含了该公司的商业模式、管理层、
行业地位、风险监管、分红回购等实时商业信息。请将这些知识作为你的行业背景
和分析上下文，用于辅助 9 模块定性打分和商业模式判断。

注意：
- 商业知识不是你重新检索的结果，而是已经准备好的输入
- 商业知识中的置信度标注（high/medium/low）反映了信息可靠性
- 低置信度的商业知识应谨慎使用，与其他数据交叉验证
- 如有矛盾，优先采信 Tushare 原始数据和财报深度分析定量结果""")

        # 第四层: 输出格式 (v0.27: 新增 full_report 字段)
        parts.append("""## 输出格式 (严格 JSON)
{
  "module_scores": {"护城河深度": 4, "管理层质量": 3, ...},
  "qualitative_total": 28,
  "module_details": [
    {
      "module": "护城河深度",
      "score": 4,
      "confidence": "high",
      "evidence": "【数据】...\\n【比较】...\\n【结论】...",
      "uncertainty": "..."
    }
  ],
  "business_model": {"judgment": "优|良|中|差", "reasoning": "...(≤300字)"},
  "red_flags": ["发现的问题1", "问题2"],
  "full_report": "完整的个性化投资分析报告文本，包含：\\n1. 公司概况与商业模式概述\\n2. 9模块逐项分析\\n3. 综合评分与风险评估\\n4. 红旗警告\\n5. 总体评价（不给出买卖建议）",
  "financial_insight_commentary": "对7个财报模块的综合解读: 收入趋势意味着什么? 利润率变化说明了什么? 现金流质量和负债结构隐藏什么信号? 把散点数据串成故事 (≤1000字)",
  "business_knowledge_synthesis": "对5类商业知识的综合判断: 护城河是否真实可持续? 管理层是否值得信任? 行业格局在变好还是变坏? 核心风险和机会是什么? (≤1000字)",
  "l3_scoring_commentary": "对十二维打分的模式点评: 哪里是护城河来源? 哪里严重拖后腿? 打分是否与商业直觉一致? 有无矛盾之处? (≤1000字)",
  "valuation_commentary": "对PR和安全边际的估值判断: 当前PR水平在合理区间吗? 安全边际率是否足够? 结合公司所处周期阶段, 估值是贵了还是便宜了? (≤1000字)"
}

重要: 每个模块的 evidence 必须使用三段式证据链:
【数据】具体定量数值
【比较】与历史或行业对比
【结论】由此推断的判断""")

        return "\n\n".join(parts)

    def _build_user_message(
        self,
        brief_md: str,
        company_name: str,
        ts_code: str,
    ) -> str:
        """构建用户消息 — v0.27: 传入完整 brief.md。

        截断过长的文本以适配 LLM 上下文窗口。
        """
        max_chars = 30000
        brief_truncated = brief_md
        if len(brief_md) > max_chars:
            brief_truncated = brief_md[:max_chars] + "\n\n...(内容已截断)"

        lines = [
            f"## 股票: {company_name} ({ts_code})",
            "",
            "以下是完整的数据底稿，包含：",
            "- 一、Tushare 原始数据（三大报表+财务指标+估值+分红）",
            "- 二、管线计算得分（L2-L5 量化打分）",
            "- 三、财报深度分析洞察（7模块 Python 确定性计算）",
            "- 四、分析报告撰写指引",
            "- 五、LLM 商业知识检索（5类商业实时信息）",
            "",
            "---",
            brief_truncated,
            "---",
            "",
            "请基于以上完整数据底稿，撰写个性化投资分析报告并输出 JSON。",
            "请充分利用 Section 5 中的商业知识作为行业背景。",
        ]
        return "\n".join(lines)

    def _apply_default_scoring(self, result: AnalysisResult) -> None:
        """LLM 不可用时使用 Python 默认打分 (保守策略)。"""
        result.success = True  # 视为"执行成功"（用默认值）
        result.error = "LLM不可用，使用Python默认保守打分"
        result.qualitative_total = 20.0
        result.module_scores = {
            mod.name: 2.5
            for mod in self._cfg.rubric.modules
        }
        result.business_model = "良"
        result.business_model_reasoning = "默认保守打分（LLM 不可用）"

    # ── v0.29: 根因反思 ──

    def diagnose_root_cause(
        self,
        cv_issues: list[dict],
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> RootCauseAnalysisResult:
        """v0.29: 对交叉验证发现的问题项做根因诊断。

        在 CV 标注 ⚠/✗/? 后，让分析 Agent 对每个问题项做二次推理，
        判断是「企业真实问题」「数据质量问题」「评估规则偏差」还是「信息不足」。

        Args:
            cv_issues: CV 问题项列表，每项含 dimension / judgment / evidence / suggestion
            brief_md: 完整 brief.md 数据底稿
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            RootCauseAnalysisResult
        """
        result = RootCauseAnalysisResult(
            ts_code=ts_code,
            name=company_name,
        )

        if not cv_issues:
            result.summary = "无 CV 问题项，不需要根因诊断"
            result.success = True
            return result

        if self._client is None:
            result.error = "LLM不可用，无法执行根因诊断"
            return result

        # 构建问题上下文
        issues_text = self._format_cv_issues(cv_issues)

        system_prompt = self._build_root_cause_system_prompt()
        user_message = self._build_root_cause_user_message(
            issues_text, brief_md, company_name, ts_code
        )

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0,
                max_tokens=32768,
            )
            result.success = True

            # 解析输出
            items_raw = raw.get("items", [])
            for item_raw in items_raw:
                rc_item = RootCauseItem(
                    dimension=item_raw.get("dimension", ""),
                    cv_judgment=item_raw.get("cv_judgment", ""),
                    cv_evidence=item_raw.get("cv_evidence", ""),
                    analysis_claim=item_raw.get("analysis_claim", ""),
                    root_cause=item_raw.get("root_cause", "信息不足"),
                    reasoning=item_raw.get("reasoning", ""),
                    confidence=item_raw.get("confidence", "medium"),
                    data_fix_suggestion=item_raw.get("data_fix_suggestion", ""),
                    enterprise_insight=item_raw.get("enterprise_insight", ""),
                )
                result.items.append(rc_item)

            # 统计
            for item in result.items:
                rc = item.root_cause
                if "企业" in rc:
                    result.enterprise_issues_count += 1
                elif "数据" in rc:
                    result.data_quality_issues_count += 1
                elif "规则" in rc or "评估" in rc or "方法" in rc:
                    result.methodology_issues_count += 1
                else:
                    result.insufficient_info_count += 1

            result.summary = raw.get("summary", "")

        except (LLMError, Exception) as e:
            logger.error(f"RootCauseDiagnosis failed: {e}")
            result.error = str(e)

        return result

    def _format_cv_issues(self, cv_issues: list[dict]) -> str:
        """将 CV 问题项格式化为分析 Agent 可读的文本。"""
        lines = []
        for i, issue in enumerate(cv_issues, 1):
            dim = issue.get("dimension", "未知维度")
            judgment = issue.get("judgment", "")
            evidence = issue.get("web_evidence", issue.get("evidence", ""))
            suggestion = issue.get("suggestion", "")
            lines.append(f"## 问题项 {i}")
            lines.append(f"- 维度: {dim}")
            lines.append(f"- CV判断: {judgment}")
            lines.append(f"- CV引用的源数据证据: {evidence}")
            if suggestion:
                lines.append(f"- CV修正建议: {suggestion}")
            lines.append("")
        return "\n".join(lines)

    def _build_root_cause_system_prompt(self) -> str:
        """v0.29: 根因反思 System Prompt。"""
        return """## 专业身份
你是同一位 CFA 持证人，拥有 15 年 A 股研究经验。
现在进入"根因反思"模式。

## 背景
在 Phase 5a 中，你基于完整 brief.md 数据底稿撰写了一份投资分析报告。
随后，事实核查员 (Phase 5b 交叉验证) 对你的分析结论进行了核查，
标注了若干 ⚠/✗/? 问题项。

## 你的任务
对每个标注的问题项进行**诊断性推理**，判断问题根源属于以下哪一类：

### 四种根因分类

1. **企业真实问题**
   公司确实存在该问题。即使数据完美、计算方法正确，结论也成立。
   例: 公司营收连续3年下滑 → 这是企业真实的业务萎缩，不是数据问题。

2. **数据质量问题**
   我们使用的数据存在过时、不完整或不准确的问题。
   例: web_search 搜到的管理层信息是 3 年前的，已不反映当前情况；
   Tushare 数据因分红送转导致列计算偏差；财报数据滞后一个季度。

3. **评估规则偏差**
   管线打分公式/评估方法对该行业/该公司不太适用，或指标关联性存疑。
   例: 高端白酒基酒需窖藏 5 年+，存货周转天数高达 1500 天是行业特征，
       不是经营效率问题；我们的存货周转打分逻辑低估了白酒行业的特殊性。

4. **信息不足无法判断**
   现有数据无法做出可靠判断，需要更多信息。
   例: 交叉验证发现分析结论与源数据之间存在冲突，但现有信息不足以确定根源。

## 核心原则
- **尽量还原企业的真实经营面貌**，剥离数据噪音和评估工具的偏差
- 如果判断为"数据质量问题"，说明缺少什么数据可以修复
- 如果判断为"评估规则偏差"，说明该行业/公司的特殊性，以及为什么我们的规则在此不适用
- 推理要具体、引用已知事实，不要泛泛而谈
- 谨慎判断"企业真实问题"——只有当企业基本面确实存在缺陷时才归入此类

## 输出格式 (严格 JSON)
{
  "items": [
    {
      "dimension": "被CV标注的维度名称",
      "cv_judgment": "⚠/✗/?",
      "cv_evidence": "CV引用的源数据证据（直接复制输入）",
      "analysis_claim": "你的分析中的原始声明（可概括）",
      "root_cause": "企业真实问题 | 数据质量问题 | 评估规则偏差 | 信息不足",
      "reasoning": "2-3句具体诊断推理，引用已知事实",
      "confidence": "high | medium | low",
      "data_fix_suggestion": "最终需要什么数据来修复（若数据问题，写清楚；否则写空字符串）",
      "enterprise_insight": "还原的企业真实情况（1-2句，尽量剥离噪音后描述企业本质）"
    }
  ],
  "summary": "整体根因判断（1-2句总结，例: 5项问题中3项为数据滞后、2项为评估偏差，分析管线整体可靠）"
}

## 注意事项
- root_cause 必须从四种分类中精确选择，不要用泛化表述
- enterprise_insight 是该维度的核心产出，请认真撰写
- cv_judgment 和 cv_evidence 直接复制输入，不要修改
- 每个问题项都要诊断，不要跳过"""

    def _build_root_cause_user_message(
        self,
        issues_text: str,
        brief_md: str,
        company_name: str,
        ts_code: str,
    ) -> str:
        """v0.29: 构建根因反思的用户消息。"""
        max_chars = 8000
        brief_truncated = brief_md
        if len(brief_md) > max_chars:
            brief_truncated = brief_md[:max_chars] + "\n\n...(内容已截断)"

        lines = [
            f"## 公司: {company_name} ({ts_code})",
            "",
            "事实核查员对你的分析报告标注了以下问题项，请你对每个问题项做根因诊断：",
            "",
            issues_text,
            "",
            "---",
            "## 原始数据底稿 (brief.md，供参考)",
            brief_truncated,
            "---",
            "",
            "请基于以上信息，对每个问题项输出根因诊断 JSON。",
        ]
        return "\n".join(lines)

    # ── v0.30: 声明提取 ──

    def extract_claims(
        self,
        analysis_text: str,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> list[AnalysisClaim]:
        """v0.30: 从分析报告中提取可核查的原子声明。

        让分析 Agent 把自己的每一条主张拆成原子声明，
        标注类型（pipeline_calculation / data_citation / trend_judgment
        / business_assertion / qualitative_score），并提供数据引用。

        Args:
            analysis_text: Phase 5a 产出的完整分析报告
            brief_md: 完整数据底稿
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            list[AnalysisClaim] 原子声明列表
        """
        if self._client is None:
            logger.warning("LLM不可用，返回空声明列表")
            return []

        # 截断 brief.md 给声明提取留出上下文
        brief_truncated = brief_md
        if len(brief_md) > 10000:
            brief_truncated = brief_md[:10000] + "\n\n...(内容已截断)"

        system_prompt = """## 声明提取任务

你仍是同一位 CFA 分析员。你已经完成了一份投资分析报告。
现在需要从你的报告中提取**核心主张**（key claims）供独立事实核查。

## 提取原则

1. **每个维度一条**：9个评估模块的每个维度（护城河深度/管理层质量/成长潜力等）只提取 **1 条** 概括性声明。
   该条声明必须**概括该维度下所有子结论**，用分号或连接词合并。
   例："品牌和技术双重护城河，毛利率稳定在28%以上远高于行业平均；但护城河宽度受限于单一业务（空调），深度评分4/5"

2. **总量控制**：全报告最多提取 **9-12 条** 核心主张（9个模块各1条 + 最多3条跨维度补充）。

3. **跳过数值引用**：不要提取 pipeline_calculation（管线Python计算的数值）和 data_citation（直接引用的原始财务数据）
   —— 这些是代码计算或对表操作，不需要 LLM 核查。

## 声明类型（仅 3 种）

1. **trend_judgment**: 趋势判断（增长/下降/改善/恶化/稳定）
   例: "营收增速连续三个季度放缓"、"盈利能力持续提升"

2. **business_assertion**: 商业知识/行业地位/管理层相关的断言
   例: "茅台护城河依赖赤水河稀缺性"、"管理层稳定未变更"

3. **qualitative_score**: 你的 9 模块主观打分声明
   例: "护城河深度 4/5 — 品牌和技术双重护城河，毛利率稳定"

## 关键要求

- 每条声明引用其在 brief.md 中的数据来源段（data_refs）
- 声明中引用的数字，记录到 source_numbers
- confidence 如实标注（high/medium/low）
- **只提取关键主张，每个维度只出1条概括声明**

## 输出格式 (严格 JSON)

{
  "claims": [
    {
      "id": "claim_01",
      "dimension": "护城河深度",
      "claim_text": "品牌+渠道+规模效应构成宽护城河，竞争对手难以复制",
      "claim_type": "business_assertion",
      "data_refs": ["brief.md §五 商业知识检索"],
      "source_numbers": {},
      "confidence": "high"
    }
  ]
}"""

        user_msg = f"""## 公司: {company_name} ({ts_code})

## 你的分析报告

{analysis_text}

---

## 数据底稿 (供参考声明提取)

{brief_truncated}

---

请从上述分析报告中提取所有关键判断声明，标注类型并提供数据引用。输出 JSON。"""

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_msg,
                temperature=0,
                max_tokens=32768,
            )
            claims: list[AnalysisClaim] = []
            for c in raw.get("claims", []):
                claims.append(AnalysisClaim(
                    id=c.get("id", ""),
                    dimension=c.get("dimension", ""),
                    claim_text=c.get("claim_text", ""),
                    claim_type=c.get("claim_type", "data_citation"),
                    data_refs=c.get("data_refs", []),
                    source_numbers=c.get("source_numbers", {}),
                    confidence=c.get("confidence", "medium"),
                ))
            logger.info(f"声明提取: {len(claims)} 条原子声明")
            return claims
        except (LLMError, Exception) as e:
            logger.error(f"声明提取失败: {e}")
            return []

    # ── v0.30: 回炉修正 ──

    def revise_with_cv_feedback(
        self,
        claims: list[AnalysisClaim],
        verified_claims: list[VerifiedClaim],
        analysis_text: str,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> tuple[list[RevisedClaim], str]:
        """v0.30: 面对 CV 核查结果做回炉修正。

        逐条审阅 CV 的核查结论，决定接受修正 / 反驳 / 澄清，
        并生成修正后的分析报告。

        Args:
            claims: 原始声明列表
            verified_claims: CV 逐条核查结果
            analysis_text: 原始分析报告
            brief_md: 完整数据底稿
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            (list[RevisedClaim], revised_report: str)
        """
        if self._client is None:
            logger.warning("LLM不可用，跳过回炉修正")
            return [], analysis_text

        # 构建 CV 反馈摘要
        cv_summary_lines = []
        for i, vc in enumerate(verified_claims, 1):
            cv_summary_lines.append(
                f"{i}. [{vc.judgment}] {vc.dimension}: {vc.claim_text if vc.claim_text else (vc.claim.claim_text if vc.claim else '')}\n"
                f"   CV证据: {vc.evidence}\n"
                f"   CV建议: {vc.suggestion}"
            )
        cv_summary = "\n\n".join(cv_summary_lines)

        system_prompt = """## 回炉修正任务

你是同一位 CFA 分析员。事实核查员 (Fact Checker) 已对你的分析报告进行了逐条核查。
现在请逐条审阅核查结果，并做出回应。

## 你的回应方式

对每一条 CV 标注，选择以下三种之一：

1. **accept (接受修正)**: CV 指出的问题确实存在，你接受修改
   → 提供 revised_text (修正后的声明文本)
2. **dispute (反驳)**: CV 的判断有误，你坚持原声明
   → 提供 rebuttal (反驳理由，引用数据)
3. **clarify (澄清)**: CV 的质疑源于误解，需要澄清但原声明本质上没有错
   → 提供 revised_text (更清晰的表述)

## 关键原则

- **学术诚实优先**: 如果 CV 是对的，坦然接受，不要防御性反驳
- **具体反驳**: 如果反驳，必须引用 brief.md 中的具体数据
- **不要删改正确的部分**: 只修正被 CV 指出的问题
- pipeline_calculation 类型的声明，如果 CV 质疑的是公式本身（而非数值抄错），应标记为 clarify，因为公式是项目规则

## 输出格式 (严格 JSON)

{
  "revised_claims": [
    {
      "claim_id": "claim_01",
      "cv_judgment": "✓源数据可支撑",
      "analyst_response": "accept",
      "revised_text": "修正后的声明文本",
      "rebuttal": ""
    }
  ],
  "revised_report": "修正后的完整分析报告全文"
}"""

        user_msg = f"""## 公司: {company_name} ({ts_code})

## 你的原始分析报告

{analysis_text}

---

## CV 事实核查结果

{cv_summary}

---

## 数据底稿 (供参考)

{brief_md[:8000] if len(brief_md) > 8000 else brief_md}

---

请逐条审阅 CV 的核查结果，对每条做出回应并生成修正后的完整分析报告。输出 JSON。"""

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_msg,
                temperature=0,
                max_tokens=32768,
            )
            revised_claims: list[RevisedClaim] = []
            for rc in raw.get("revised_claims", []):
                claim_id = rc.get("claim_id", "")
                # 找到对应的原始声明
                original_claim = None
                for c in claims:
                    if c.id == claim_id:
                        original_claim = c
                        break
                revised_claims.append(RevisedClaim(
                    claim=original_claim,
                    claim_id=claim_id,
                    cv_judgment=rc.get("cv_judgment", ""),
                    cv_evidence=rc.get("cv_evidence", ""),
                    analyst_response=rc.get("analyst_response", "accept"),
                    revised_text=rc.get("revised_text", ""),
                    rebuttal=rc.get("rebuttal", ""),
                ))

            revised_report = raw.get("revised_report", analysis_text)
            logger.info(
                f"回炉修正: {len(revised_claims)} 条, "
                f"accept={sum(1 for r in revised_claims if r.analyst_response == 'accept')}, "
                f"dispute={sum(1 for r in revised_claims if r.analyst_response == 'dispute')}, "
                f"clarify={sum(1 for r in revised_claims if r.analyst_response == 'clarify')}"
            )
            return revised_claims, revised_report
        except (LLMError, Exception) as e:
            logger.error(f"回炉修正失败: {e}")
            return [], analysis_text
