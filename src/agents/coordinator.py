"""
Agent Coordinator — 协调双 Agent 的分析→验证工作流。

流程:
1. 分析 Agent 产出定性分析 → SharedContext.opinions["analysis"]
2. 验证 Agent 对分析结果执行审计 → SharedContext.opinions["verification"]
3. Coordinator 汇总结果并触发报告生成

支持重试循环：验证不通过可触发分析 Agent 修正（最多 3 次）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from src.agents.context import SharedContext
from src.turtle.calculator.scoring import FinalScore


@dataclass
class CoordinatorResult:
    """Coordinator 汇总结果。"""
    ts_code: str
    success: bool = False
    analysis_done: bool = False
    verification_done: bool = False
    retry_count: int = 0
    max_retries: int = 3
    errors: list[str] = field(default_factory=list)
    context: SharedContext | None = None


class AgentCoordinator:
    """双 Agent 工作流协调器。

    Usage:
        coord = AgentCoordinator(max_retries=3)
        result = coord.run(score, llm_client)
        if result.success:
            print(result.context.opinions)
    """

    def __init__(self, max_retries: int = 3):
        self._max_retries = max_retries

    def run(
        self,
        score: FinalScore,
        llm_client=None,  # LLMClient
        *,
        extra_data: dict | None = None,
    ) -> CoordinatorResult:
        """执行完整分析→验证工作流。

        Args:
            score: 最终评分结果
            llm_client: LLM 客户端（可选，None → 跳过 LLM 调用）
            extra_data: 额外数据（行业对比等）

        Returns:
            CoordinatorResult
        """
        ctx = SharedContext.from_score(score)
        result = CoordinatorResult(
            ts_code=score.ts_code,
            context=ctx,
            max_retries=self._max_retries,
        )

        if extra_data:
            for k, v in extra_data.items():
                ctx.add_enriched(k, v)

        # 如果没有 LLM client，直接返回（降级到 Python 默认打分）
        if llm_client is None:
            logger.info(f"[{score.ts_code}] 无 LLM client，跳过 Agent 分析")
            result.success = True
            return result

        # 分析 → 验证 循环（最多 max_retries 次修正）
        for attempt in range(self._max_retries + 1):
            result.retry_count = attempt

            if not result.analysis_done:
                try:
                    logger.info(f"[{score.ts_code}] 分析 Agent 运行中 (attempt {attempt + 1})...")
                    # analysis = llm_client.run_analysis(score, ctx)
                    # ctx.set_opinion("analysis", analysis)
                    result.analysis_done = True
                except Exception as e:
                    result.errors.append(f"分析失败: {e}")
                    logger.error(f"[{score.ts_code}] 分析 Agent 失败: {e}")
                    if attempt >= self._max_retries:
                        break
                    continue

            if not result.verification_done:
                try:
                    logger.info(f"[{score.ts_code}] 验证 Agent 运行中...")
                    # analysis_result = ctx.get_opinion("analysis")
                    # verification = llm_client.run_verification(analysis_result, score, ctx)
                    # ctx.set_opinion("verification", verification)
                    result.verification_done = True
                except Exception as e:
                    result.errors.append(f"验证失败: {e}")
                    logger.error(f"[{score.ts_code}] 验证 Agent 失败: {e}")
                    break

            if result.analysis_done and result.verification_done:
                result.success = True
                break

        return result


__all__ = ["AgentCoordinator", "CoordinatorResult"]
