"""
CLI 入口 — stock-analyze 命令。

Usage:
    stock-analyze 600519.SH           # 分析单只股票
    stock-analyze 600519.SH --llm     # 启用 LLM Agent 分析
    stock-analyze 600519.SH --html    # 生成 HTML 报告
"""

from __future__ import annotations

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="龟龟投资策略 — A股选股到报告生成全管线",
    )
    parser.add_argument("ts_code", nargs="?", help="股票代码 (如 600519.SH)")
    parser.add_argument("--llm", action="store_true", help="启用 LLM Agent 分析/验证")
    parser.add_argument("--html", action="store_true", help="输出 HTML 报告")
    parser.add_argument("--output", "-o", default="", help="报告输出路径")
    parser.add_argument("--token", help="Tushare Token (可选，默认读 .env)")

    args = parser.parse_args()

    if not args.ts_code:
        parser.print_help()
        return

    if args.token:
        os.environ["TUSHARE_TOKEN"] = args.token

    from src.data_fetcher.tushare_client import TushareClient
    from src.calculator.turtle_strategy.scoring import TurtleScorer

    print(f"🐢 龟龟策略 v0.15 — 分析 {args.ts_code}")
    print("=" * 60)

    # Phase 2: 量化打分
    print("[Phase 2] 量化打分...")
    try:
        client = TushareClient()
        scorer = TurtleScorer(client)
        result = scorer.score(args.ts_code)
    except Exception as e:
        print(f"[ERROR] 打分失败: {e}")
        sys.exit(1)

    print(f"  L2={result.l2_score}  L3=×{result.l3_multiplier}  L4={result.l4_score}  L5={result.l5_score}")
    print(f"  Raw={result.raw_total}  Final={result.final_score}  Pool={result.pool}")
    print(f"  PR={result.pr_pct:.2f}%  OE={result.oe_quality}  仓位={result.position_pct}%")

    orchestration = None

    # Phase 3: LLM Agent (可选)
    if args.llm:
        print("\n[Phase 3] LLM Agent 分析...")
        from src.llm.orchestrator import AgentOrchestrator
        from src.llm.client import LLMConfig

        if not LLMConfig.is_configured():
            print("  [SKIP] 未配置 LLM API Key (设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY)")
        else:
            orch = AgentOrchestrator()
            orchestration = orch.run(result)
            if orchestration.analysis and orchestration.analysis.success:
                print(f"  分析Agent: {orchestration.analysis.qualitative_total}/45  {orchestration.analysis.business_model}")
            if orchestration.verification and orchestration.verification.success:
                print(f"  验证Agent: {orchestration.verification.overall_verdict}  "
                      f"通过率={orchestration.verification.fact_check_pass_rate:.0f}%")

    # Phase 4: 报告
    if args.html:
        print("\n[Report] 生成 HTML 报告...")
        from src.reporter.report_generator import ReportGenerator

        gen = ReportGenerator()
        output = args.output or f"report_{args.ts_code.replace('.', '_')}.html"
        gen.save(result, output, orchestration)
        print(f"  报告已保存: {output}")

    print("\n✅ 分析完成")


if __name__ == "__main__":
    main()
