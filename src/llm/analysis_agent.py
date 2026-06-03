"""
分析 Agent — CFA 价值投资研究员 v1.1 (v0.27 重构)。

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

from src.llm.client import LLMClient, LLMConfig, LLMError
from src.rules.loader import load_rules


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

    # 状态
    success: bool = False
    error: str = ""

    # 原始 LLM 输出 (调试用)
    raw_output: dict[str, Any] = field(default_factory=dict)


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
            result.full_report = raw.get("full_report", "")

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
  "full_report": "完整的个性化投资分析报告文本，包含：\\n1. 公司概况与商业模式概述\\n2. 9模块逐项分析\\n3. 综合评分与风险评估\\n4. 红旗警告\\n5. 总体评价（不给出买卖建议）"
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
        max_chars = 14000
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
