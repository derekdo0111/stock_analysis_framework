"""报告渲染器 — 将分析结果渲染为 HTML/MD。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from src.turtle.calculator.scoring import FinalScore


class ReportRenderer:
    """报告渲染器基类 — 支持 HTML 和 Markdown 格式。

    Usage:
        renderer = ReportRenderer(template_dir="src/reporter/templates")
        html = renderer.render_html(score, analysis_text, verification_text)
    """

    def __init__(self, template_dir: str | Path = "src/reporter/templates"):
        self._template_dir = Path(template_dir)

    def render_html(
        self,
        score: FinalScore,
        analysis_text: str = "",
        verification_text: str = "",
        *,
        extra_context: dict | None = None,
    ) -> str:
        """渲染 HTML 报告。

        Args:
            score: 最终评分结果
            analysis_text: 分析 Agent 输出
            verification_text: 验证 Agent 输出
            extra_context: 额外模板变量

        Returns:
            HTML 字符串
        """
        try:
            from jinja2 import Environment, FileSystemLoader

            env = Environment(
                loader=FileSystemLoader(str(self._template_dir)),
                autoescape=True,
            )

            template_name = "analysis_report.html"
            template = env.get_template(template_name)

            context = {
                "ts_code": score.ts_code,
                "name": score.name,
                "l2_score": score.l2_score,
                "l3_multiplier": score.l3_multiplier,
                "l4_score": score.l4_score,
                "l5_score": score.l5_score,
                "raw_total": score.raw_total,
                "final_score": score.final_score,
                "pool": score.pool,
                "pr_pct": score.pr_pct,
                "oe_quality": score.oe_quality,
                "analysis": analysis_text,
                "verification": verification_text,
            }
            if extra_context:
                context.update(extra_context)

            return template.render(**context)

        except Exception as e:
            logger.error(f"HTML 渲染失败: {e}")
            return self._fallback_html(score, analysis_text, verification_text)

    def render_markdown(
        self,
        score: FinalScore,
        analysis_text: str = "",
        verification_text: str = "",
    ) -> str:
        """渲染 Markdown 报告。"""
        lines = [
            f"# {score.name} ({score.ts_code}) 分析报告",
            "",
            "## 评分概览",
            "",
            f"| 层级 | 得分 |",
            f"|------|------|",
            f"| L2 初筛 | {score.l2_score:.1f} / 20 |",
            f"| L3 商业模式 | ×{score.l3_multiplier:.1f} |",
            f"| L4 穿透回报率 | {score.l4_score:.1f} / 40 |",
            f"| L5 安全边际 | {score.l5_score:.1f} / 25 |",
            f"| **原始总分** | **{score.raw_total:.1f}** |",
            f"| **最终得分** | **{score.final_score:.1f}** |",
            f"| 归属池 | **{score.pool}** |",
            "",
            f"PR: {score.pr_pct:.2%} | OE质量: {score.oe_quality}",
            "",
        ]

        if analysis_text:
            lines.append("## 分析 Agent 输出")
            lines.append("")
            lines.append(analysis_text)
            lines.append("")

        if verification_text:
            lines.append("## 验证 Agent 输出")
            lines.append("")
            lines.append(verification_text)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fallback_html(
        score: FinalScore,
        analysis_text: str = "",
        verification_text: str = "",
    ) -> str:
        """Jinja2 不可用时的降级 HTML。"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{score.name} 分析报告</title></head>
<body>
<h1>{score.name} ({score.ts_code})</h1>
<table border="1">
<tr><th>层级</th><th>得分</th></tr>
<tr><td>L2</td><td>{score.l2_score:.1f}/20</td></tr>
<tr><td>L3</td><td>×{score.l3_multiplier:.1f}</td></tr>
<tr><td>L4</td><td>{score.l4_score:.1f}/40</td></tr>
<tr><td>L5</td><td>{score.l5_score:.1f}/25</td></tr>
<tr><td><b>最终</b></td><td><b>{score.final_score:.1f}</b></td></tr>
<tr><td>归属池</td><td>{score.pool}</td></tr>
</table>
<pre>{analysis_text}</pre>
<pre>{verification_text}</pre>
</body></html>"""


__all__ = ["ReportRenderer"]
