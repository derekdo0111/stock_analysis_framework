"""
LLM 交叉验证 Agent — 商业知识检索 + 三维交叉验证。

v0.25 重写：
- 合并商业知识检索和交叉验证为一次 LLM 调用
- 三维对比：管线得分 vs 财报深度分析洞察 vs LLM 训练知识
- 降级链：API LLM → Python 规则引擎

用法:
    from src.llm.cross_validation_agent import CrossValidationAgent
    agent = CrossValidationAgent()
    result = agent.validate(brief_md_text, company_name, ts_code)
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
    """单条不一致记录。"""
    dimension: str           # 维度名
    quantitative_score: str   # 管线得分
    evidence: str             # 证据（来自财报洞察或 LLM 知识）
    judgment: str             # "矛盾" / "一致" / "信息补充"
    suggestion: str           # 修正建议
    severity: str = "INFO"   # INFO / WARNING / CRITICAL
    # v0.24 兼容字段
    web_evidence: str = ""    # deprecated, 使用 evidence 替代


@dataclass
class BusinessKnowledgeResult:
    """LLM 商业知识检索结果。"""
    ts_code: str
    name: str

    business_model: str = ""      # 商业模式与护城河
    management: str = ""          # 管理层与治理
    industry_position: str = ""   # 行业地位
    risk_regulation: str = ""     # 风险与监管
    dividend_buyback: str = ""    # 分红与回购

    source: str = "unavailable"   # "api_llm" / "fallback" / "unavailable"


@dataclass
class CrossValidationResult:
    """交叉验证结果。"""

    ts_code: str
    name: str = ""

    # 逐条不一致记录
    discrepancies: list[Discrepancy] = field(default_factory=list)

    # 汇总
    total_checked: int = 0
    consistent_count: int = 0
    conflict_count: int = 0
    supplement_count: int = 0

    # 建议修正后的得分
    suggested_l3_adjustment: float = 0.0
    suggested_l4_adjustment: float = 0.0
    suggested_l5_adjustment: float = 0.0

    # 总结
    overall_verdict: str = ""
    key_findings: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

    # LLM 商业知识
    business_knowledge: BusinessKnowledgeResult | None = None

    # 状态
    success: bool = False
    error: str = ""
    used_fallback: bool = False


# ══════════════════════════════════════════════════════════════
# LLM 交叉验证 System Prompt (v0.25 重写：三维对比)
# ══════════════════════════════════════════════════════════════

_CV_SYSTEM_PROMPT_V25 = """你是一位资深投资研究分析师。请完成两项任务：

## 任务一：商业知识检索
基于你对这家公司的训练数据知识，回答以下 5 类商业问题（每类 2-3 句话，标注置信度 high/medium/low）：

1. **商业模式与护城河**：核心业务、盈利模式、竞争优势
2. **管理层与治理**：管理层背景、股权结构、治理评价、近期变动/争议
3. **行业地位**：行业排名、市场份额、竞争格局
4. **风险与监管**：已知风险、监管问询、诉讼、财务争议
5. **分红与回购**：分红政策、股东回报历史、回购公告

对于你不确定的信息，标注置信度 low。不要编造不存在的具体数字。

## 任务二：三维交叉验证
对比以下三类信息，逐维标注矛盾或一致：

1. **管线计算得分** (Section 2) — 基于 Tushare 财务数据的量化打分
2. **财报深度分析洞察** (Section 3) — 从三大报表提取的趋势/质量
3. **你的商业知识** (任务一输出) — LLM 训练数据中的商业判断

重点检查：
- 管线得分是否与财报趋势一致？（如：ROE得分高但财报显示ROE实际在下降 → 矛盾）
- 你的商业知识是否支持或质疑管线得分？（如：你知晓管理层负面，但得分给满分 → 矛盾）
- 财报洞察是否揭示管线未捕捉到的风险？（如：现金流质量恶化但未在得分中体现 → 信息补充）

对每条不一致输出：dimension, quantitative_score, evidence, judgment(矛盾/一致/信息补充), suggestion, severity(INFO/WARNING/CRITICAL)

输出格式：严格的 JSON：
{
  "business_knowledge": {
    "business_model": "商业模式分析...",
    "business_model_confidence": "high|medium|low",
    "management": "管理层分析...",
    "management_confidence": "high|medium|low",
    "industry_position": "行业地位分析...",
    "industry_position_confidence": "high|medium|low",
    "risk_regulation": "风险监管分析...",
    "risk_regulation_confidence": "high|medium|low",
    "dividend_buyback": "分红回购分析...",
    "dividend_buyback_confidence": "high|medium|low"
  },
  "discrepancies": [
    {
      "dimension": "L3 ROE稳定性",
      "quantitative_score": "2/2",
      "evidence": "财报显示ROE从30.2%降至28.7%，近3年持续下降",
      "judgment": "矛盾",
      "suggestion": "建议下调ROE稳定性得分至1/2",
      "severity": "WARNING"
    }
  ],
  "overall_verdict": "总体结论",
  "key_findings": ["发现1", "发现2"],
  "red_flags": ["红旗1"],
  "suggested_l3_adjustment": 0.0,
  "suggested_l4_adjustment": 0.0,
  "suggested_l5_adjustment": 0.0
}

注意：
- suggested_l3/l4/l5_adjustment 是建议对最终得分加减的分值（可正可负）
- 如果某类知识你不确定，confidence 标为 low，不要强行编造
- 不要编造财报或 brief 中不存在的信息
"""


# ══════════════════════════════════════════════════════════════
# 降级规则引擎（无 LLM 时使用）
# ══════════════════════════════════════════════════════════════


def _fallback_validate(
    brief_md: str,
    company_name: str = "",
    ts_code: str = "",
) -> CrossValidationResult:
    """降级规则引擎 — 财报洞察 vs 管线得分简单对比。"""
    result = CrossValidationResult(
        ts_code=ts_code,
        name=company_name,
        success=True,
        used_fallback=True,
    )

    discrepancies: list[Discrepancy] = []

    # 检查 brief.md 是否包含财报洞察
    has_financial_insights = "## 三、财报深度分析洞察" in brief_md

    if not has_financial_insights:
        result.overall_verdict = "财报深度分析数据缺失，无法执行交叉验证"
        result.key_findings = ["财报深度分析未执行或数据不可用"]
        result.success = False
        result.error = "无财报深度分析数据"
        return result

    # 简单规则：关键词检测
    checks = [
        ("ROE趋势与得分一致", "ROE", "下降"),
        ("现金流质量", "现金流质量=优秀", "现金流质量=差劲"),
        ("资产负债健康度", "稳健", "危险"),
        ("分红连续性", "连续分红", ""),
        ("利润率趋势", "改善", "恶化"),
    ]

    for dim_desc, positive_kw, negative_kw in checks:
        if positive_kw in brief_md:
            has_positive = True
        else:
            has_positive = False

        has_negative = bool(negative_kw) and negative_kw in brief_md

        if has_negative:
            discrepancies.append(Discrepancy(
                dimension=f"财报洞察 - {dim_desc}",
                quantitative_score="需 LLM 分析",
                evidence=f"检测到可能的问题: {negative_kw}",
                judgment="信息补充",
                suggestion=f"检测到{dim_desc}可能存在问题，需 LLM 进一步分析",
                severity="WARNING",
            ))

    result.discrepancies = discrepancies
    result.total_checked = len(checks)
    result.supplement_count = len(discrepancies)
    result.overall_verdict = (
        f"降级规则引擎: 扫描 {len(checks)} 个维度，"
        f"发现 {len(discrepancies)} 个可能需注意的项"
    )
    result.key_findings = [
        "⚠️ 当前使用降级规则引擎，仅做简单关键词扫描",
        "建议配置 DEEPSEEK_API_KEY 以获得 LLM 商业知识分析和准确的交叉验证",
    ]

    return result


# ══════════════════════════════════════════════════════════════
# 交叉验证 Agent
# ══════════════════════════════════════════════════════════════


class CrossValidationAgent:
    """LLM 交叉验证 Agent (v0.25 重写)。

    读取 brief.md（含财报洞察），调用 LLM 完成：
    1. 5 类商业知识检索
    2. 三维交叉验证（管线得分 vs 财报洞察 vs LLM知识）

    降级：无 API Key → Python 规则引擎。
    """

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient()
        self._client = client

    def validate(
        self,
        brief_md: str,
        company_name: str = "",
        ts_code: str = "",
    ) -> CrossValidationResult:
        """执行商业知识检索 + 交叉验证。

        Args:
            brief_md: brief.md 全文（含 Section 1 Tushare + Section 2 得分 + Section 3 财报洞察）
            company_name: 公司名称
            ts_code: 股票代码

        Returns:
            CrossValidationResult 含不一致记录、修正建议、商业知识
        """
        if self._client is None:
            logger.info("LLM 不可用，使用降级规则引擎")
            return _fallback_validate(brief_md, company_name, ts_code)

        # 截断过长的文本
        max_chars = 16000
        if len(brief_md) > max_chars:
            brief_md = brief_md[:max_chars] + "\n\n...(内容已截断)"

        user_prompt = f"""请分析以下股票：{company_name or ts_code} ({ts_code})

以下是数据底稿，包含管线得分和财报深度分析洞察：

{brief_md}

请完成 5 类商业知识检索 + 三维交叉验证。输出 JSON 格式结果。"""

        try:
            response = self._client.chat(
                system_prompt=_CV_SYSTEM_PROMPT_V25,
                user_message=user_prompt,
                temperature=0.0,
                response_format="json_object",  # type: ignore[call-arg]
            )
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")
            return _fallback_validate(brief_md, company_name, ts_code)

        return self._parse_response(response, brief_md, company_name, ts_code)

    def _parse_response(
        self,
        response_text: str,
        brief_md: str,
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

        # ── 解析商业知识 ──
        bk_data = data.get("business_knowledge", {})
        if bk_data:
            result.business_knowledge = BusinessKnowledgeResult(
                ts_code=ts_code,
                name=company_name,
                business_model=bk_data.get("business_model", ""),
                management=bk_data.get("management", ""),
                industry_position=bk_data.get("industry_position", ""),
                risk_regulation=bk_data.get("risk_regulation", ""),
                dividend_buyback=bk_data.get("dividend_buyback", ""),
                source="api_llm",
            )

        # ── 解析 discrepancies ──
        disc_list = data.get("discrepancies", [])
        for d in disc_list:
            result.discrepancies.append(Discrepancy(
                dimension=d.get("dimension", ""),
                quantitative_score=d.get("quantitative_score", ""),
                evidence=d.get("evidence", d.get("web_evidence", "")),
                judgment=d.get("judgment", "信息补充"),
                suggestion=d.get("suggestion", ""),
                severity=d.get("severity", "INFO"),
            ))

        # ── 统计 ──
        result.total_checked = len(result.discrepancies)
        result.consistent_count = sum(
            1 for d in result.discrepancies if d.judgment == "一致"
        )
        result.conflict_count = sum(
            1 for d in result.discrepancies if d.judgment == "矛盾"
        )
        result.supplement_count = sum(
            1 for d in result.discrepancies if d.judgment == "信息补充"
        )

        # ── 修正建议 ──
        result.suggested_l3_adjustment = float(data.get("suggested_l3_adjustment", 0))
        result.suggested_l4_adjustment = float(data.get("suggested_l4_adjustment", 0))
        result.suggested_l5_adjustment = float(data.get("suggested_l5_adjustment", 0))

        # ── 总结 ──
        result.overall_verdict = data.get("overall_verdict", "")
        result.key_findings = data.get("key_findings", [])
        result.red_flags = data.get("red_flags", [])

        result.success = True
        return result
