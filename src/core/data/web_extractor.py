"""
Web + LLM 结构化提取器 — v0.19 新增 Layer 3 数据源。

轻量提取（方案A）：给公告文本 → LLM → Pydantic 结构化输出，不做推理判断。

用途:
- 提取分红比率承诺（公告检索 → 结构化数字）
- 提取回购注销确认（公告检索 → 注销金额）

所有数据提取在 DataPoolOrchestrator._fetch_all() 中完成，
结果写入 StockDataBundle，后续模块只读不调 API。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class DividendCommitment:
    """分红比率承诺提取结果。"""

    has_commitment: bool = False
    ratio: float | None = None  # 承诺的分红比率 (%)
    source: str = ""  # 公告标题/URL
    period: str = ""  # 承诺覆盖期，e.g. "2024-2026"


@dataclass
class BuybackCancellation:
    """回购注销确认提取结果。"""

    has_cancellation: bool = False
    amount: float = 0.0  # 注销金额（万元）
    source: str = ""  # 公告标题/URL


class WebExtractor:
    """数据获取阶段的轻量 LLM 提取器。

    与末端 Agent 不同，此提取器只做结构化实体提取，不做推理判断。

    用法:
        extractor = WebExtractor()
        commitment = extractor.extract_dividend_commitment("600519.SH", "贵州茅台")
        buyback = extractor.extract_buyback_cancellation("600519.SH", "贵州茅台")
    """

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    # ── Public API ──────────────────────────────────────────

    def extract_dividend_commitment(
        self, ts_code: str, name: str, search_results: list[str] | None = None
    ) -> DividendCommitment:
        """搜索分红承诺公告 → LLM 提取结构化数据。

        Args:
            ts_code: 股票代码
            name: 股票名称
            search_results: 预先获取的公告文本列表（可选）。
                            如果为 None，返回空结果（需外部先完成搜索）。

        Returns:
            DividendCommitment
        """
        if not search_results:
            return DividendCommitment(has_commitment=False)

        # 拼接所有搜索结果作为 LLM 输入
        combined_text = "\n\n---\n\n".join(search_results[:3])

        try:
            extracted = self._llm_extract(combined_text, "dividend_commitment")
            if extracted and extracted.get("has_commitment"):
                return DividendCommitment(
                    has_commitment=True,
                    ratio=float(extracted.get("ratio", 0)),
                    source=extracted.get("source", ""),
                    period=extracted.get("period", ""),
                )
        except Exception:
            pass

        return DividendCommitment(has_commitment=False)

    def extract_buyback_cancellation(
        self, ts_code: str, name: str, search_results: list[str] | None = None
    ) -> BuybackCancellation:
        """搜索回购注销公告 → LLM 提取注销金额。

        Args:
            ts_code: 股票代码
            name: 股票名称
            search_results: 预先获取的公告文本列表（可选）。

        Returns:
            BuybackCancellation
        """
        if not search_results:
            return BuybackCancellation(has_cancellation=False)

        combined_text = "\n\n---\n\n".join(search_results[:3])

        try:
            extracted = self._llm_extract(combined_text, "buyback_cancellation")
            if extracted and extracted.get("has_cancellation"):
                return BuybackCancellation(
                    has_cancellation=True,
                    amount=float(extracted.get("amount", 0)),
                    source=extracted.get("source", ""),
                )
        except Exception:
            pass

        return BuybackCancellation(has_cancellation=False)

    # ── LLM 提取核心 ───────────────────────────────────────

    def _llm_extract(self, text: str, extract_type: str) -> dict[str, Any] | None:
        """调用 LLM 提取结构化数据。

        使用项目已有的 LLM 基础设施。如 LLM 不可用，返回 None。
        """
        try:
            from src.core.llm.client import LLMClient, LLMConfig

            if not LLMConfig.is_configured():
                # 无 LLM，返回 None（外推降级到 tier2）
                return None

            client = LLMClient()

            prompt = self._build_extraction_prompt(text, extract_type)
            raw = client.complete(
                prompt,
                temperature=0,
                max_tokens=512,
                json_mode=True,
            )

            return json.loads(raw) if raw else None
        except Exception:
            return None

    def _build_extraction_prompt(self, text: str, extract_type: str) -> str:
        """构建轻量提取 prompt — 只做实体提取，不做分析判断。"""

        if extract_type == "dividend_commitment":
            return f"""你是一个财务数据提取器。从以下公告文本中提取结构化数据，不要做任何分析或判断。

公告内容：
{text[:8000]}

提取要求：
1. 查找分红比率承诺：如「不低于XX%」「XX%以上」「分红比例不低于XX%」「每年以现金方式分配的利润不少于XX%」等表述
2. 查找承诺覆盖期：如「2024-2026年」「未来三年」
3. 如果有明确数字承诺，has_commitment=true，填写 ratio（百分比数字）
4. 如果没有明确数字承诺，has_commitment=false

严格按以下 JSON 格式输出，不要输出其他内容：
{{"has_commitment": true或false, "ratio": 数字或null, "source": "公告标题或空字符串", "period": "覆盖期或空字符串"}}"""

        elif extract_type == "buyback_cancellation":
            return f"""你是一个财务数据提取器。从以下公告文本中提取结构化数据，不要做任何分析或判断。

公告内容：
{text[:8000]}

提取要求：
1. 查找回购注销相关表述：「回购注销」「减少注册资本」「用于注销」「回购股份并注销」
2. 查找注销金额（万元）或回购金额中明确用于注销的部分
3. 注意区分「回购用于股权激励」和「回购注销」——只有明确用于注销/减资的才算

严格按以下 JSON 格式输出，不要输出其他内容：
{{"has_cancellation": true或false, "amount": 数字(万元)或0, "source": "公告标题或空字符串"}}"""

        return ""

    # ── 搜索辅助（供外部 orchestrator 调用） ────────────────

    @staticmethod
    def build_search_queries(name: str) -> dict[str, str]:
        """构建搜索关键词。

        Returns:
            {"dividend": "搜索词", "buyback": "搜索词"}
        """
        return {
            "dividend": f"{name} 分红承诺 股东回报规划",
            "buyback": f"{name} 回购注销 公告",
        }


__all__ = ["WebExtractor", "DividendCommitment", "BuybackCancellation"]
