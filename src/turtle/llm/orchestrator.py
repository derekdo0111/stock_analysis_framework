"""
Agent 协作编排器 — 分析→验证→修正→降级默认打分。

工作流:
1. AnalysisAgent: 基于Python计算结果+财务数据 → 9模块分析
2. VerificationAgent: 对分析输出执行10项审计程序 → 验证报告
3. 如果 overall.verdict = "部分修正" → 分析Agent修正不可靠模块 (最多3次)
4. 如果 3次重试后 still "不可靠" → 降级为Python默认打分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.core.llm.client import LLMClient, LLMConfig
from src.turtle.llm.analysis_agent import AnalysisAgent, AnalysisResult
from src.turtle.llm.verification_agent import VerificationAgent, VerificationResult
from src.turtle.calculator.scoring import FinalScore


@dataclass
class OrchestrationResult:
    """编排器最终输出。"""
    ts_code: str
    name: str = ""

    # 量化结果
    final_score: FinalScore | None = None

    # 分析 Agent 输出
    analysis: AnalysisResult | None = None

    # 验证 Agent 输出
    verification: VerificationResult | None = None

    # 协作状态
    retries: int = 0
    used_fallback: bool = False
    fallback_reason: str = ""

    # 最终结论
    final_verdict: str = ""  # "通过" / "部分修正" / "不可靠"
    executive_summary: str = ""


class AgentOrchestrator:
    """双Agent协作编排器。"""

    def __init__(self, client: LLMClient | None = None):
        if client is None and LLMConfig.is_configured():
            client = LLMClient()
        self._client = client
        self._analysis = AnalysisAgent(client)
        self._verification = VerificationAgent(client)

    def run(
        self,
        final_score: FinalScore,
        profile: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> OrchestrationResult:
        """运行完整 Agent 协作管线。"""
        result = OrchestrationResult(
            ts_code=final_score.ts_code,
            name=final_score.name,
            final_score=final_score,
        )

        # ── Step 1: 分析 ──
        analysis = self._analysis.analyze(final_score, profile)
        result.analysis = analysis

        if isinstance(analysis, AnalysisResult):
            pass  # already assigned

        if not analysis.success:
            result.fallback_reason = f"分析Agent失败: {analysis.error}"
            result.final_verdict = "不可靠"
            return result

        # ── Step 2: 验证 ──
        verification = self._verification.verify(analysis, profile)
        result.verification = verification

        if not verification.success:
            result.fallback_reason = "验证Agent失败"
            result.final_verdict = "不可靠"
            return result

        # ── Step 3: 修正循环 ──
        retries = 0
        current_verdict = verification.overall_verdict

        while current_verdict == "部分修正" and retries < max_retries:
            logger.info(f"修正循环 {retries + 1}/{max_retries}")
            # 标记不可靠模块，要求分析Agent修正
            unreliable_modules = [
                f["module"]
                for f in verification.fact_checks
                if not f.get("verified", True)
            ]
            analysis = self._analysis.analyze(
                final_score,
                {
                    **(profile or {}),
                    "fix_modules": unreliable_modules,
                    "verification_feedback": verification.executive_summary,
                },
            )
            verification = self._verification.verify(analysis, profile)
            current_verdict = verification.overall_verdict
            retries += 1

        result.retries = retries
        result.final_verdict = current_verdict
        result.executive_summary = verification.executive_summary

        # ── Step 4: 降级处理 ──
        if current_verdict == "不可靠":
            result.used_fallback = True
            result.fallback_reason = f"经过{retries}次修正仍不可靠，使用Python默认分"
            logger.warning(f"Agent阅卷不可靠，回退Python默认分: {final_score.ts_code}")

        return result
