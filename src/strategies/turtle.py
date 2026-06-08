"""龟龟策略适配器 — 将 src/turtle/ 现有管线包装为 BaseStrategy 接口。

hink: 龟龟是第一个也是目前唯一完整实现的策略。
Web 层通过此适配器调用龟龟的筛选、分析和报告生成。
"""

from __future__ import annotations

from src.strategies.base import BaseStrategy


class TurtleStrategy(BaseStrategy):
    """龟龟投资策略 — L2-L5 完整量化管线 + LLM 多Agent分析。

    这是项目的旗舰策略，覆盖:
    - HardGate 6 项否决 + 公司分类
    - L2 初筛 (FQ/估值/流动性/分红)
    - L3 十二维商业模式打分
    - L4 穿透回报率 (PR) + OE 双路径
    - L5 安全边际 + 仓位建议
    - LLM 三阶段: 商业检索 → CFA分析 → 交叉验证
    - HTML 完整报告 (含 SOTP 估值 & 现金对账)
    """

    slug = "turtle"
    name = "龟龟策略"
    description = "龟龟投资策略 v0.35 — L2-L5 完整量化管线 + LLM 多Agent分析"
    schedule = "30 15 * * 5"  # 每周五 15:30 (收盘后)

    def screen(self, client) -> "pd.DataFrame":
        """全A筛选 → 候选池。

        调用 src/turtle/screening/run_screener.py 的筛选管线。
        """
        import pandas as pd
        from src.turtle.screening.run_screener import run_full_screening

        return run_full_screening(client)

    def analyze(self, ts_code: str) -> dict:
        """个股完整分析。

        运行 stock-analyze 管线（Phase 1-6），返回摘要 dict。
        """
        import sys
        from io import StringIO

        # 调用 CLI main
        from src.turtle.cli import main as turtle_main

        # 简化版: 只返回核心指标
        # 完整分析需要通过 subprocess 或直接调用管线函数
        return {
            "ts_code": ts_code,
            "status": "not_implemented_via_api",
            "note": "请通过 CLI 'stock-analyze {ts_code} --html' 运行完整分析",
        }

    def build_report(self, ts_code: str) -> str:
        """生成 HTML 报告路径。"""
        from pathlib import Path

        code_part = ts_code.replace(".", "_")
        # 假设报告已由 CLI 生成
        report_dir = Path("output") / code_part
        html_files = list(report_dir.glob("report_*.html"))
        if html_files:
            return str(html_files[-1])
        return ""
