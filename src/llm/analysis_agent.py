"""
分析 Agent — CFA 价值投资研究员 v1.0。

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

import pandas as pd
from loguru import logger

from src.llm.client import LLMClient, LLMConfig, LLMError
from src.rules.loader import load_rules
from src.calculator.turtle_strategy.scoring import FinalScore


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

    # 状态
    success: bool = False
    error: str = ""

    # 原始 LLM 输出 (调试用)
    raw_output: dict[str, Any] = field(default_factory=dict)


class AnalysisAgent:
    """CFA 价值投资研究员 — 9模块定性分析。"""

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient()
        self._client = client
        self._rules = load_rules()
        self._cfg = self._rules.agent_constraints.analysis_agent

    def analyze(
        self,
        final_score: FinalScore,
        profile: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """对一只股票执行 9 模块定性分析。

        Args:
            final_score: 阶段二乘法打分结果
            profile: 额外 Python 计算数据
        """
        result = AnalysisResult(
            ts_code=final_score.ts_code,
            name=final_score.name,
        )

        if self._client is None:
            result.error = "LLM not configured (no API key)"
            self._apply_default_scoring(result, final_score)
            return result

        # 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(final_score, profile)

        try:
            raw = self._client.chat_json(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0,
                max_tokens=4096,
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

        except (LLMError, Exception) as e:
            logger.error(f"AnalysisAgent failed: {e}")
            result.error = str(e)
            self._apply_default_scoring(result, final_score)

        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示词 — 注入四层约束。"""
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
{must}

### 禁止行为
{must_not}""")

        # 第三层: Rubric 量表 (简化版)
        rubric_lines = []
        for mod in cfg.rubric.modules:
            rubric_lines.append(f"### {mod.name} (0-5分)")
            rubric_lines.append(f"{mod.description}")
            for s in mod.scale[:3]:  # 只展示前3个等级节省 token
                rubric_lines.append(f"  {s.score}分: {s.description[:80]}")
        parts.append("## 打分量表\n" + "\n".join(rubric_lines))

        # 第四层: 输出格式
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
  "red_flags": ["发现的问题1", "问题2"]
}

重要: 每个模块的 evidence 必须使用三段式证据链:
【数据】具体定量数值
【比较】与历史或行业对比
【结论】由此推断的判断""")

        return "\n\n".join(parts)

    def _build_user_message(
        self, fs: FinalScore, profile: dict[str, Any] | None
    ) -> str:
        """构建用户消息 — 注入 Python 计算结果。"""
        lines = [
            f"## 股票: {fs.name} ({fs.ts_code})",
            "",
            "### 量化打分结果 (阶段二 Python 计算)",
            f"- L2 初筛得分: {fs.l2_score}/20",
            f"- L3 商业模式乘数: {fs.l3_multiplier}",
            f"- L4 穿透回报率得分: {fs.l4_score}/40",
            f"- L5 安全边际得分: {fs.l5_score}/25",
            f"- 最终得分: {fs.final_score}",
            f"- 所属池: {fs.pool}",
            f"- 穿透回报率: {fs.pr_pct:.2f}%",
            f"- OE 质量标签: {fs.oe_quality}",
            f"- 建议仓位: {fs.position_pct}%",
        ]
        if profile:
            lines.append("\n### 补充数据")
            for k, v in profile.items():
                lines.append(f"- {k}: {v}")

        lines.append("\n请基于以上量化数据和你的专业判断，输出9模块分析JSON。")
        return "\n".join(lines)

    def _apply_default_scoring(self, result: AnalysisResult, fs: FinalScore) -> None:
        """LLM 失败时使用 Python 默认打分 (保守策略)。"""
        result.success = False
        # 基于 L2 分和 L3 乘数估算定性分
        base = fs.l2_score / 20.0 * 5.0  # 将L2映射到0-5量级
        result.qualitative_total = round(base * 9, 1)  # 9模块
        result.module_scores = {
            mod.name: round(base, 1)
            for mod in self._cfg.rubric.modules
        }
        result.business_model = fs.business_model
