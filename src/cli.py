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

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _a(s: str) -> str:
    """Replace emoji with ASCII-safe equivalents for Windows GBK console."""
    return s.replace("\U0001f7e2", "[OK]").replace("\U0001f7e1", "[?]").replace("\U0001f534", "[!!]")


def _out_dir(ts_code: str, name: str = "") -> str:
    """返回默认输出子目录路径，自动创建。
    
    格式: output/{代码}_{名称}/  如 output/600519_SH_贵州茅台/
    """
    code_part = ts_code.replace(".", "_")
    if name:
        folder = f"{code_part}_{name}"
    else:
        folder = code_part
    d = os.path.join("output", folder)
    os.makedirs(d, exist_ok=True)
    return d


def main():
    parser = argparse.ArgumentParser(
        description="龟龟投资策略 — A股选股到报告生成全管线",
    )
    parser.add_argument("ts_code", nargs="?", help="股票代码 (如 600519.SH)")
    parser.add_argument("--llm", action="store_true", help="启用 LLM Agent 分析/验证")
    parser.add_argument("--html", action="store_true", help="输出 HTML 完整报告")
    parser.add_argument("--brief", action="store_true", help="输出 HTML 简报（含数据溯源+管线推导）")
    parser.add_argument("--cross-validate", action="store_true", help="执行财报深度分析 + LLM商业知识检索 + 三维交叉验证")
    parser.add_argument("--output", "-o", default="", help="报告输出路径")
    parser.add_argument("--token", help="Tushare Token (可选，默认读 .env)")

    args = parser.parse_args()

    if not args.ts_code:
        parser.print_help()
        return

    if args.token:
        os.environ["TUSHARE_TOKEN"] = args.token

    from src.data_fetcher.tushare_client import TushareClient
    from src.data_fetcher.orchestrator import DataPoolOrchestrator
    from src.calculator.turtle_strategy.scoring import TurtleScorer

    print(f"[Turtle] v0.25 -- Analyzing {args.ts_code}")
    print("=" * 60)

    # Phase 1: 数据快照（唯一调用 Tushare 的入口）
    print("[Phase 1] 数据快照...")
    try:
        client = TushareClient(token=args.token or None)
        orch = DataPoolOrchestrator(client)
        snap_result = orch.snapshot_stock(args.ts_code)
        if not snap_result.success:
            print(f"[ERROR] 数据快照失败: {snap_result.errors}")
            sys.exit(1)
        print(f"  已拉取 {snap_result.datasets_stored} 个数据集")
        bundle = orch.get_bundle(args.ts_code)
        if bundle is None:
            print(f"[ERROR] 无法加载缓存数据")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 数据拉取失败: {e}")
        sys.exit(1)

    # Phase 2: 量化打分（纯读缓存）
    print("[Phase 2] 量化打分...")
    try:
        scorer = TurtleScorer(bundle)
        result = scorer.score(args.ts_code)
    except Exception as e:
        print(f"[ERROR] 打分失败: {e}")
        sys.exit(1)

    print(f"  L2(门控)={result.l2_score}  L3={result.l3_score}/30 ({result.l3_level})  L4={result.l4_score}/45  L5={result.l5_score}/25")
    print(f"  Final={result.final_score}/100  Pool={result.pool}")
    print(f"  PR={result.pr_pct:.2f}%  OE={_a(result.oe_quality)}  仓位={result.position_pct}%")
    if result.pr_distribution_source:
        src_label = "承诺" if "tier1" in result.pr_distribution_source else "外推"
        print(f"  分配比率={result.pr_distribution_ratio:.1f}%({src_label})  可支配现金={result.pr_disposable_cash:.0f}万  回购注销={result.pr_buyback_cancellation:.0f}万")

    orchestration = None
    cv_result = None
    financial_insights = None

    # Phase 3-6 (v0.25 NEW): 财报深度分析 + LLM 商业知识检索 + 交叉验证
    if args.cross_validate:
        print("\n[Phase 3] 财报深度分析 (7模块)...")
        from src.calculator.financial_deep_analysis import FinancialDeepAnalyzer
        try:
            fa = FinancialDeepAnalyzer(bundle)
            financial_insights = fa.analyze()
            print(f"  模块1 收入利润: {financial_insights.revenue_trend_str[:80]}...")
            print(f"  模块2 利润率:   {financial_insights.margin_trend_str[:80]}...")
            print(f"  模块3 ROE杜邦:  {financial_insights.roe_trend_str[:80]}...")
            print(f"  模块4 现金流:   {financial_insights.cash_quality_str[:80]}...")
            print(f"  模块5 资产负债: {financial_insights.balance_health_str[:80]}...")
            print(f"  模块6 分红政策: {financial_insights.dividend_policy_str[:80]}...")
            print(f"  模块7 营运效率: {financial_insights.efficiency_str[:80]}...")
            # 缓存
            orch.cache_financial_insights(args.ts_code, financial_insights)
        except Exception as e:
            print(f"  [WARN] 财报深度分析失败: {e}")

        print("\n[Phase 4] 组装 brief.md 数据底稿...")
        from src.reporter.brief_md_builder import BriefMDBuilder
        builder = BriefMDBuilder(bundle, result, financial_insights)
        brief_md = builder.build()

        brief_md_path = args.output.replace(".html", "_brief.md") if args.output else os.path.join(_out_dir(args.ts_code, bundle.name), f"brief_{args.ts_code.replace('.', '_')}.md")
        with open(brief_md_path, "w", encoding="utf-8") as f:
            f.write(brief_md)
        print(f"  brief.md 已保存: {brief_md_path}")

        print("\n[Phase 5] LLM 商业知识检索 + 三维交叉验证...")
        from src.llm.cross_validation_agent import CrossValidationAgent
        from src.llm.client import LLMConfig
        if not LLMConfig.is_configured():
            print("  [INFO] 未配置 LLM API Key，使用降级规则引擎")
        else:
            print(f"  [INFO] LLM Provider: {LLMConfig.provider() or 'auto'} / Model: {LLMConfig.model()}")

        cv_agent = CrossValidationAgent()
        cv_result = cv_agent.validate(brief_md, bundle.name, args.ts_code)
        if cv_result.success:
            print(f"  检查维度: {cv_result.total_checked}")
            print(f"  一致: {cv_result.consistent_count} | 矛盾: {cv_result.conflict_count} | 信息补充: {cv_result.supplement_count}")
            if cv_result.business_knowledge:
                print(f"  商业知识: LLM 检索完成 ({cv_result.business_knowledge.source})")
            if cv_result.red_flags:
                for rf in cv_result.red_flags:
                    print(f"    [!!] {rf}")
        else:
            print(f"  [WARN] 交叉验证失败: {cv_result.error}")

    # Phase 6: 交叉验证 HTML 报告
    if args.cross_validate and cv_result and cv_result.success:
        print("\n[Phase 6] 生成交叉验证 HTML 报告...")
        from src.reporter.report_generator import ReportGenerator
        gen = ReportGenerator()
        output = args.output or os.path.join(_out_dir(args.ts_code, bundle.name), f"cv_{args.ts_code.replace('.', '_')}.html")
        gen.save_cross_validated(result, cv_result, financial_insights, output, orchestration)
        print(f"  交叉验证报告已保存: {output}")

    # Phase 3 (OLD): LLM Agent (可选)
    if args.llm:
        print("\n[Phase 3] LLM Agent 分析...")
        from src.llm.orchestrator import AgentOrchestrator
        from src.llm.client import LLMConfig

        if not LLMConfig.is_configured():
            print("  [INFO] 未配置 LLM API Key，使用本地规则引擎分析")
        else:
            print(f"  [INFO] LLM Provider: {LLMConfig.provider() or 'auto'} / Model: {LLMConfig.model()}")

        orch = AgentOrchestrator()
        orchestration = orch.run(result)
        if orchestration.analysis and orchestration.analysis.success:
            tags = "[LLM]" if LLMConfig.is_configured() else "[本地引擎]"
            print(f"  分析Agent: {orchestration.analysis.qualitative_total}/45  "
                  f"({orchestration.analysis.business_model}) {tags}")
            # 打印 9 模块明细
            if orchestration.analysis.module_details:
                for md in orchestration.analysis.module_details:
                    name = md.get("module", "?")
                    s = md.get("score", 0)
                    conf = md.get("confidence", "?")
                    evidence_short = (md.get("evidence", "")[:60] + "...") if md.get("evidence") else ""
                    bar = "#" * s + "-" * (5 - s)
                    print(f"    {bar} {name}: {s}/5 ({conf})")
            if orchestration.analysis.red_flags:
                for rf in orchestration.analysis.red_flags:
                    print(f"    🔴 {rf}")
        elif orchestration.analysis:
            print(f"  分析Agent: 默认打分 {orchestration.analysis.qualitative_total}/45  [PYTHON-DEFAULT]")
        if orchestration.verification and orchestration.verification.success:
            print(f"  验证Agent: {orchestration.verification.overall_verdict}  "
                  f"通过率={orchestration.verification.fact_check_pass_rate:.0f}%")
        else:
            print(f"  验证Agent: SKIP (无需 LLM 验证 Python 默认分)")
        if orchestration.used_fallback:
            print(f"  [WARN] 降级: {orchestration.fallback_reason}")

    # Phase 4: 报告
    if args.html:
        print("\n[Report] 生成 HTML 完整报告...")
        from src.reporter.report_generator import ReportGenerator

        gen = ReportGenerator()
        output = args.output or os.path.join(_out_dir(args.ts_code, bundle.name), f"report_{args.ts_code.replace('.', '_')}.html")
        gen.save(result, output, orchestration)
        print(f"  完整报告已保存: {output}")

    if args.brief:
        print("\n[Brief] 生成 HTML 简报（数据溯源+管线推导）...")
        from src.reporter.report_generator import ReportGenerator

        gen = ReportGenerator()
        output = args.output or os.path.join(_out_dir(args.ts_code, bundle.name), f"brief_{args.ts_code.replace('.', '_')}.html")
        gen.save_brief(bundle, result, output)
        print(f"  简报已保存: {output}")

    # 打印详细分解
    print(f"\n  --- Breakdown ---")
    print(f"  HardGate: {'PASS' if result.hard_gate_passed else 'VETO'}")
    print(f"  L2(门控): {result.l2_details}")
    print(f"  Classify: {result.classify_type}")
    print(f"  L3: {result.l3_score}/30 ({result.l3_level})  dim-score={result.l3_total_dim}/24")
    print(f"  L4 PR: {result.pr_pct:.2f}%  start={result.pr_starting_score}  penalty={result.pr_quality_penalty}  OE={_a(result.oe_quality)}")
    print(f"  PR: DC={result.pr_disposable_cash:.0f}万  ratio={result.pr_distribution_ratio:.1f}%({result.pr_distribution_source})  buyback={result.pr_buyback_cancellation:.0f}万")
    print(f"  L5 估值安全边际率: {result.l5_safety_margin_pct:.1f}%  估值得分: {result.l5_valuation_score}/15  缓冲: {result.l5_downside_score}/5")
    print(f"  L5 仓位: {result.position_pct}%")

    print("\n[DONE] Analysis complete.")


if __name__ == "__main__":
    main()
