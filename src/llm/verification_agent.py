"""
验证 Agent — CPA+CFE 审计师 v1.0。

从 agent_constraints.yaml 加载:
- 第一层: 专业身份 (CPA+CFE, 前四大审计, 10年审计经验+3年FDD)
- 第二层: 行为边界 (职业怀疑/量化差异/追溯核查/不自行调和矛盾)
- 第三层: 10项标准审计程序
- 第四层: Schema 硬约束 + 报告标记格式

核心作用: 逐条核查分析Agent的声明，输出 ✓/✗ + 证据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.llm.client import LLMClient, LLMConfig, LLMError
from src.llm.analysis_agent import AnalysisResult
from src.rules.loader import load_rules


@dataclass
class VerificationResult:
    """验证 Agent 输出。"""
    ts_code: str

    # 事实核查
    fact_checks: list[dict[str, Any]] = field(default_factory=list)
    fact_check_pass_rate: float = 0.0

    # 数据问题发现
    data_issues: list[dict[str, Any]] = field(default_factory=list)

    # 一致性检查
    consistency_flags: list[dict[str, Any]] = field(default_factory=list)

    # 综合裁决
    overall_verdict: str = "通过"  # 通过 / 部分修正 / 不可靠
    requires_human_review: bool = False
    executive_summary: str = ""

    # 状态
    success: bool = False
    error: str = ""
    raw_output: dict[str, Any] = field(default_factory=dict)


class VerificationAgent:
    """CPA+CFE 审计师 — 对分析 Agent 输出执行 10 项审计程序。"""

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient()
        self._client = client
        self._rules = load_rules()
        self._cfg = self._rules.agent_constraints.verification_agent

    def verify(
        self,
        analysis: AnalysisResult,
        original_data: dict[str, Any] | None = None,
    ) -> VerificationResult:
        """验证分析 Agent 的输出。

        Args:
            analysis: 分析Agent的完整输出
            original_data: 原始财务数据 (用于事实核查对比)
        """
        result = VerificationResult(ts_code=analysis.ts_code)

        if self._client is None:
            result.error = "LLM not configured"
            result.overall_verdict = "不可靠"
            result.executive_summary = "Agent不可用，已使用Python默认值"
            return result

        # 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(analysis, original_data)

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0,
                max_tokens=4096,
            )
            result.raw_output = raw
            result.success = True

            result.fact_checks = raw.get("fact_checks", [])
            result.fact_check_pass_rate = float(raw.get("fact_check_pass_rate", 0))
            result.data_issues = raw.get("data_issues", [])
            result.consistency_flags = raw.get("consistency_flags", [])
            result.overall_verdict = str(raw.get("overall", {}).get("verdict", "部分修正"))
            result.requires_human_review = bool(raw.get("overall", {}).get("requires_human_review", False))
            result.executive_summary = str(raw.get("overall", {}).get("executive_summary", ""))

        except (LLMError, Exception) as e:
            logger.error(f"VerificationAgent failed: {e}")
            result.error = str(e)
            result.overall_verdict = "不可靠"
            result.executive_summary = f"验证Agent失败: {e}"

        return result

    def _build_system_prompt(self) -> str:
        cfg = self._cfg
        parts = []

        # 身份
        role = cfg.role
        parts.append(f"""## 专业身份
你是 {role.title}，拥有 {role.experience}。
核心理念: {role.core_belief}""")

        # 行为边界
        must = "\n".join([f"- {m.rule}" for m in cfg.behavior.must_do])
        must_not = "\n".join([f"- {m.rule}" for m in cfg.behavior.must_not_do])
        parts.append(f"""## 行为边界
### 必须做到
{must}
### 禁止
{must_not}""")

        # 输出格式
        parts.append("""## 输出格式 (严格 JSON)
{
  "fact_checks": [
    {
      "module": "模块名",
      "claim": "分析Agent的声明",
      "verified": true,
      "evidence": "验证依据 (通过: 原始数据确认; 不通过: 原始数据XX vs 声明YY)",
      "severity": "INFO|WARNING|CRITICAL (仅不通过时填写)"
    }
  ],
  "fact_check_pass_rate": 75.0,
  "data_issues": [{"audit_program": "程序名", "finding": "发现", "severity": "等级", "evidence": "证据"}],
  "consistency_flags": [{"module_a": "A", "module_b": "B", "contradiction": "矛盾描述"}],
  "overall": {
    "verdict": "通过|部分修正|不可靠",
    "requires_human_review": false,
    "executive_summary": "≤500字总结"
  }
}

重要:
- ✓ 验证通过的条目必须明确标注，并列出验证依据
- ✗ 不通过的条目必须列出矛盾点和原始数据对比
- 严重程度: INFO(轻微)/WARNING(需关注)/CRITICAL(破坏性矛盾)
- 至少1个CRITICAL → requires_human_review=true""")

        return "\n\n".join(parts)

    def _build_user_message(
        self, analysis: AnalysisResult, original_data: dict[str, Any] | None
    ) -> str:
        lines = [
            f"## 待验证股票: {analysis.name} ({analysis.ts_code})",
            "",
            "### 分析Agent的评分和判断",
            f"总评: {analysis.qualitative_total}/45",
            f"商业模式: {analysis.business_model}",
        ]

        for detail in analysis.module_details:
            lines.append(
                f"\n#### {detail.get('module', '')}: {detail.get('score', '?')}分 "
                f"(confidence={detail.get('confidence', '?')})"
            )
            lines.append(f"证据: {detail.get('evidence', 'N/A')}")
            lines.append(f"不确定因素: {detail.get('uncertainty', '')}")

        if analysis.red_flags:
            lines.append("\n### 红旗警告")
            for f in analysis.red_flags:
                lines.append(f"- {f}")

        if original_data:
            lines.append("\n### 原始财务数据 (用于事实核查)")
            for k, v in list(original_data.items())[:20]:
                lines.append(f"- {k}: {v}")

        lines.append("\n请执行10项审计程序，输出验证结果JSON。")
        return "\n".join(lines)
