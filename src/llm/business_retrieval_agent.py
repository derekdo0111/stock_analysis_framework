"""
商业知识检索 Agent — Phase 3.5。

使用 LLM + web_search tool calling 获取公司实时商业信息。
5 类商业问题，每类至少 1 次搜索，标注置信度 + 来源 URL。

用法:
    from src.llm.business_retrieval_agent import BusinessRetrievalAgent
    agent = BusinessRetrievalAgent()
    result = agent.retrieve(ts_code="600519.SH", company_name="贵州茅台", ...)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from src.llm.client import LLMClient, LLMConfig, LLMError

# ══════════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════════


@dataclass
class BusinessKnowledgeResult:
    """商业知识检索结果。"""

    ts_code: str
    name: str

    # 5 类商业知识
    business_model: str = ""
    business_model_confidence: str = "low"

    management: str = ""
    management_confidence: str = "low"

    industry_position: str = ""
    industry_position_confidence: str = "low"

    risk_regulation: str = ""
    risk_regulation_confidence: str = "low"

    dividend_buyback: str = ""
    dividend_buyback_confidence: str = "low"

    # 搜索结果来源
    source_urls: list[str] = field(default_factory=list)

    # 检索元数据
    source: str = "unavailable"  # api_llm | fallback | unavailable
    retrieved_at: str = ""

    # 状态
    success: bool = False
    error: str = ""

    def to_markdown(self) -> str:
        """转为 brief.md Section 5 的 Markdown 格式。"""
        if self.source == "unavailable":
            return (
                "\n\n## 五、LLM 商业知识检索\n\n"
                "*(商业知识检索未执行: API 不可用)*\n"
            )

        source_note = ""
        if self.source == "fallback":
            source_note = " *(仅基于 LLM 训练数据，无实时搜索)*"

        lines = [
            "",
            "## 五、LLM 商业知识检索",
            "",
            f"**来源**: {self.source}{source_note}",
            f"**检索时间**: {self.retrieved_at}",
            "",
            f"### 5.1 商业模式与护城河 (置信度: {self.business_model_confidence})",
            self.business_model or "*(无数据)*",
            "",
            f"### 5.2 管理层与治理 (置信度: {self.management_confidence})",
            self.management or "*(无数据)*",
            "",
            f"### 5.3 行业地位 (置信度: {self.industry_position_confidence})",
            self.industry_position or "*(无数据)*",
            "",
            f"### 5.4 风险与监管 (置信度: {self.risk_regulation_confidence})",
            self.risk_regulation or "*(无数据)*",
            "",
            f"### 5.5 分红与回购 (置信度: {self.dividend_buyback_confidence})",
            self.dividend_buyback or "*(无数据)*",
            "",
        ]

        if self.source_urls:
            lines.append("### 搜索来源")
            for url in self.source_urls:
                lines.append(f"- {url}")
            lines.append("")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════════

_BR_SYSTEM_PROMPT = """你是一位资深商业分析师，负责检索并整理上市公司的实时商业信息。

你可以使用 web_search 工具搜索互联网获取最新信息。请按以下 5 个类别逐一搜索和分析：

## 工作流程
1. 对每个类别至少发起 1 次 web_search（优先 search_type=news 获取近2年信息）
2. 基于搜索结果 + 你的训练数据知识，撰写 2-4 句话的分析
3. 标注置信度（high/medium/low）+ 引用来源 URL

## 5 类商业问题

### 1. 商业模式与护城河
核心业务、盈利模式、竞争优势、品牌价值、客户粘性、护城河变化

### 2. 管理层与治理
管理层背景与稳定性、股权结构、治理评价、近期高管变动、争议事件

### 3. 行业地位
行业排名、市场份额、竞争格局变化、行业周期位置

### 4. 风险与监管
已知风险（行业/公司层面）、监管问询/处罚、诉讼、财务争议、ESG问题

### 5. 分红与回购
分红政策（承诺比率/频率）、股东回报历史、回购公告及执行情况

## 规则
- 优先使用 web_search 返回的实时信息，训练数据作为补充
- 不确定的信息标注 confidence=low，并说明不确定的原因
- 不要编造具体数字（营收、利润、份额百分比等），除非搜索结果明确提供
- 每类知识需要标注至少 1 个来源 URL

## 输出格式（严格 JSON）
{
  "business_model": "分析内容...",
  "business_model_confidence": "high|medium|low",
  "management": "分析内容...",
  "management_confidence": "high|medium|low",
  "industry_position": "分析内容...",
  "industry_position_confidence": "high|medium|low",
  "risk_regulation": "分析内容...",
  "risk_regulation_confidence": "high|medium|low",
  "dividend_buyback": "分析内容...",
  "dividend_buyback_confidence": "high|medium|low",
  "source_urls": ["https://...", "https://..."]
}"""


# ══════════════════════════════════════════════════════════════
# 降级模式（无 API 时从训练数据生成）
# ══════════════════════════════════════════════════════════════

_BR_FALLBACK_PROMPT = """你是一位资深商业分析师。请基于你对以下公司的训练数据知识，回答 5 类商业问题。

注意：
- 你无法搜索实时信息，仅基于训练数据
- 每类 2-3 句话，标注置信度 high/medium/low
- 不确定的信息标注 confidence=low，不要编造数字
- source_urls 留空

输出严格 JSON 格式。"""


# ══════════════════════════════════════════════════════════════
# Agent
# ══════════════════════════════════════════════════════════════


class BusinessRetrievalAgent:
    """商业知识检索 Agent — Phase 3.5。

    使用 LLM + web_search tool calling 获取实时商业信息。
    降级: 无 API Key → 跳过；搜索不可用 → 仅 LLM 训练数据。
    """

    def __init__(self, client: LLMClient | None = None):
        model = LLMConfig.retrieval_model()
        if client is None and LLMConfig.is_configured():
            client = LLMClient(model=model)
        self._client = client

    def retrieve(
        self,
        ts_code: str,
        company_name: str = "",
        industry: str = "",
        market_cap: float = 0,
        revenue: float = 0,
    ) -> BusinessKnowledgeResult:
        """执行 5 类商业知识检索。

        Args:
            ts_code: 股票代码 (如 600519.SH)
            company_name: 公司名称
            industry: 所属行业 (如 "白酒")
            market_cap: 总市值 (亿元)
            revenue: 营收 (亿元)

        Returns:
            BusinessKnowledgeResult
        """
        result = BusinessKnowledgeResult(
            ts_code=ts_code,
            name=company_name,
        )

        if self._client is None:
            logger.info("LLM 不可用，跳过商业知识检索")
            result.source = "unavailable"
            result.error = "LLM API Key 未配置"
            return result

        # 检查搜索可用性
        from src.llm.tools import _search_provider
        search_available = _search_provider() != "none"

        if search_available:
            # 全功能模式: LLM + web_search tool calling
            return self._retrieve_with_search(result, ts_code, company_name, industry, market_cap, revenue)
        else:
            # 降级模式: 仅 LLM 训练数据
            return self._retrieve_fallback(result, ts_code, company_name, industry, market_cap, revenue)

    def _retrieve_with_search(
        self,
        result: BusinessKnowledgeResult,
        ts_code: str,
        company_name: str,
        industry: str,
        market_cap: float,
        revenue: float,
    ) -> BusinessKnowledgeResult:
        """全功能模式: LLM + tool calling。"""
        from src.llm.tools import BUSINESS_RETRIEVAL_TOOLS, execute_tool

        user_msg = self._build_user_message(
            company_name, ts_code, industry, market_cap, revenue
        )

        try:
            # 使用 chat_with_tools 进行多轮搜索
            raw_text = self._client.chat_with_tools(
                system_prompt=_BR_SYSTEM_PROMPT,
                user_message=user_msg,
                tools=BUSINESS_RETRIEVAL_TOOLS,
                tool_executor=execute_tool,
                temperature=0.3,
                max_turns=5,
                max_tokens=4096,
            )

            # 解析 JSON
            data = self._parse_json(raw_text)
            self._populate_result(result, data)
            result.source = "api_llm"
            result.retrieved_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            result.success = True

        except (LLMError, Exception) as e:
            logger.warning(f"商业检索失败: {e}，尝试降级")
            return self._retrieve_fallback(result, ts_code, company_name, industry, market_cap, revenue)

        return result

    def _retrieve_fallback(
        self,
        result: BusinessKnowledgeResult,
        ts_code: str,
        company_name: str,
        industry: str,
        market_cap: float,
        revenue: float,
    ) -> BusinessKnowledgeResult:
        """降级模式: 仅 LLM 训练数据，无搜索。"""
        user_msg = self._build_user_message(
            company_name, ts_code, industry, market_cap, revenue
        )
        user_msg += "\n\n注意: 你无法搜索实时信息，请仅基于训练数据回答。"

        try:
            raw = self._client.chat_json(
                system_prompt=_BR_FALLBACK_PROMPT,
                user_message=user_msg,
                temperature=0.3,
                max_tokens=4096,
            )
            self._populate_result(result, raw)
            result.source = "fallback"
            result.retrieved_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            result.success = True

        except (LLMError, Exception) as e:
            logger.warning(f"商业检索降级也失败: {e}")
            result.source = "unavailable"
            result.error = str(e)

        return result

    @staticmethod
    def _build_user_message(
        company_name: str,
        ts_code: str,
        industry: str = "",
        market_cap: float = 0,
        revenue: float = 0,
    ) -> str:
        lines = [f"请检索以下公司的商业信息: {company_name} ({ts_code})"]
        if industry:
            lines.append(f"行业: {industry}")
        if market_cap:
            lines.append(f"总市值: {market_cap:.0f} 亿元")
        if revenue:
            lines.append(f"营收: {revenue:.0f} 亿元")
        lines.append("\n请按 5 个类别逐一使用 web_search 搜索，输出 JSON。")
        return "\n".join(lines)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """解析 LLM 返回的 JSON，处理 markdown 代码块包裹。"""
        text = text.strip()
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()
        return json.loads(text)

    @staticmethod
    def _populate_result(result: BusinessKnowledgeResult, data: dict) -> None:
        """从 JSON dict 填充 BusinessKnowledgeResult。"""
        result.business_model = data.get("business_model", "")
        result.business_model_confidence = data.get("business_model_confidence", "low")
        result.management = data.get("management", "")
        result.management_confidence = data.get("management_confidence", "low")
        result.industry_position = data.get("industry_position", "")
        result.industry_position_confidence = data.get("industry_position_confidence", "low")
        result.risk_regulation = data.get("risk_regulation", "")
        result.risk_regulation_confidence = data.get("risk_regulation_confidence", "low")
        result.dividend_buyback = data.get("dividend_buyback", "")
        result.dividend_buyback_confidence = data.get("dividend_buyback_confidence", "low")
        result.source_urls = data.get("source_urls", [])
