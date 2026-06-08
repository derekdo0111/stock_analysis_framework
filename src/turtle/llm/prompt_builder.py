"""Prompt Builder — 为分析/验证 Agent 构建结构化 prompt。"""

from __future__ import annotations

from src.turtle.calculator.scoring import FinalScore


class PromptBuilder:
    """LLM Prompt 构建器。

    将规则、评分数据、约束条件组装为标准 prompt。
    """

    @staticmethod
    def build_analysis_prompt(
        score: FinalScore,
        rules_context: str = "",
        extra_data: dict | None = None,
    ) -> list[dict[str, str]]:
        """构建分析 Agent 的 messages。

        Args:
            score: 最终评分结果
            rules_context: 从 RuleInjector 注入的规则文本
            extra_data: 额外数据（如行业对比、历史趋势等）

        Returns:
            OpenAI-compatible messages list
        """
        system_msg = (
            "你是一位 CFA 持证人，专注 A 股价值投资分析，拥有 15 年经验。\n"
            "请对以下股票进行 9 模块定性分析。每个结论必须使用三段式证据链格式：\n"
            "【数据】→【比较】→【结论】\n\n"
            f"{rules_context}"
        )

        data_parts = [
            f"股票: {score.name} ({score.ts_code})",
            f"L2 初筛得分: {score.l2_score:.1f}/20",
            f"L4 穿透回报率: {score.l4_score:.1f}/40 (PR={score.pr_pct:.2%})",
            f"L5 安全边际: {score.l5_score:.1f}/25",
            f"L3 商业模式乘数: ×{score.l3_multiplier:.1f}",
            f"最终得分: {score.final_score:.1f}",
            f"归属池: {score.pool}",
            f"OE质量: {score.oe_quality}",
        ]

        if extra_data:
            for k, v in extra_data.items():
                data_parts.append(f"{k}: {v}")

        user_msg = "\n".join(data_parts)

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    @staticmethod
    def build_verification_prompt(
        analysis_result: str,
        score: FinalScore,
        rules_context: str = "",
    ) -> list[dict[str, str]]:
        """构建验证 Agent 的 messages。

        Args:
            analysis_result: 分析 Agent 的输出文本
            score: 最终评分结果
            rules_context: 审计程序规则文本

        Returns:
            OpenAI-compatible messages list
        """
        system_msg = (
            "你是一位 CPA+CFE 持证人，前四大审计经理，10 年审计经验 + 3 年 FDD 经验。\n"
            "请对以下分析结果执行 10 项审计程序验证。\n"
            "每个程序必须标注通过(✓)或不通过(✗)，并提供验证依据。\n\n"
            f"{rules_context}"
        )

        user_msg = (
            f"股票: {score.name} ({score.ts_code})\n"
            f"最终得分: {score.final_score:.1f}\n\n"
            f"=== 待验证的分析结果 ===\n"
            f"{analysis_result}"
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]


__all__ = ["PromptBuilder"]
